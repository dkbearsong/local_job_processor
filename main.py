# Libraries
import csv
import os
import sys
from typing import List, Optional
import pypdf
from docx import Document
import google.genai as genai
from openai import OpenAI
from pydantic import BaseModel, Field
import asyncio
from langchain_core.prompts import PromptTemplate
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import logging

# Modules
from app.logger import setup_logging, exception_handler
from app.postgres_ssh_connector import execute_query_with_env_vars
from app.report_generator import generate_job_report
from app.lm_connector import create_lm_connection
from app.langchain_caller import LangchainConnector
from app.resume_generator import generate_resume_workflow

# FastAPI App Setup
app = FastAPI(title="Local Job Processor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_logging("project_errors.log")
sys.excepthook = exception_handler

# Mock Response Class for Offline/Test mode
class MockResponse:
    def __init__(self, text: str):
        self.text = text

############################## Helper Functions ####################################

def connect_gemini(gem_key: str | None):
    """Builds a connection to Google Gemini's API to make requests and returns the client."""
    try:
        client = genai.Client(api_key=gem_key)
        return client
    except Exception as e:
        print(f"Gemini connection error: {e}")
        return None

def connect_lms(lm_api: str):
    """Builds a connection to a local install of LM Studio, taking in the API path as a variable and returns the client."""
    try:
        # LM Studio uses an OpenAI-compatible endpoint
        client = OpenAI(base_url=lm_api, api_key="lm-studio")
        return client
    except Exception as e:
        print(f"LM Studio connection error: {e}")
        return None
    
def create_sql_query(job_title: str, company_name: str, type: str, limit: int = 3, minusDays: int = 7):
    sql_query = f'''
    SELECT j.id, j.job_name, c.company_name, j.job_summary
    FROM job j
    JOIN company c
    ON j.company_id = c.id
    JOIN office o
    ON j.office_id = o.id
    WHERE (j.skip IS NULL OR j.skip = False) 
    {f"AND j.job_name LIKE '%{job_title}%'" if type == 'job' else f"AND c.company_name LIKE '%{company_name}%'" if type == 'company' else f""}
    AND j.job_summary IS NOT NULL
    AND j.date_added >= CURRENT_DATE - INTERVAL '{minusDays} days'  
    AND (o.country IN ('USA', 'United States', 'US') OR o.location LIKE '%Remote%' AND o.country = 'NA') 
    LIMIT {limit};
    '''
    return sql_query

def pull_sql_data(query: str):
    results = execute_query_with_env_vars(query)
    # We keep the full row dict so we can reference job_id and job_name later
    jl = [row for row in results]
    jd = [row['job_summary'] for row in jl if 'job_summary' in row]
    return jl, jd

def load_jobs_from_csv(csv_path: str):
    required_fields = {'id', 'job_name', 'company_name', 'job_summary'}
    with open(csv_path, newline='', encoding='utf-8') as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row.")

        headers = {field.strip().lower() for field in reader.fieldnames if field}
        missing_fields = required_fields - headers
        if missing_fields:
            raise ValueError(f"CSV file is missing required fields: {', '.join(sorted(missing_fields))}")

        jobs = []
        descriptions = []
        for row in reader:
            normalized = {key.strip().lower(): (value or '').strip() for key, value in row.items() if key}
            if not normalized.get('job_summary'):
                continue
            jobs.append({
                'id': normalized.get('id', ''),
                'job_name': normalized.get('job_name', ''),
                'company_name': normalized.get('company_name', ''),
                'job_summary': normalized.get('job_summary', ''),
            })
            descriptions.append(normalized.get('job_summary', ''))

        if not jobs:
            raise ValueError("CSV file contains no valid jobs with a job_summary.")

    return jobs, descriptions

def file_to_string(file_name):
    if file_name.endswith(".pdf"):
        with open(file_name, 'rb') as open_file:
            file_reader = pypdf.PdfReader(open_file)
            text = ""
            for page in file_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    elif file_name.endswith(".docx"):
        file_reader = Document(file_name)
        text = "\n".join([paragraph.text for paragraph in file_reader.paragraphs])
        return text
    elif file_name.lower().endswith(".txt"):
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read().strip()
    else:
        raise ValueError(f"Unsupported file format: {file_name}. Please provide a .pdf or .docx file.")

async def invoke_with_retry(chain, inputs, validator, max_retries=3):
    for attempt in range(max_retries):
        try:
            output = await chain.ainvoke(inputs)
            if validator(output):
                return output
            else:
                print(f"  Validation failed on attempt {attempt + 1}")
        except Exception as e:
            print(f"  Error on attempt {attempt + 1}: {e}")
    raise Exception(f"Failed after {max_retries} attempts")


############################## API Endpoints ####################################

class JobFit(BaseModel):
    job_id: str
    job_name: str
    company_name: str
    matching_skills: List[str]
    missing_skills: List[str]
    match_score: int = Field(description="Score from 0-100")
    reasoning: str = Field(description="Brief explanation of why this is a top match")

class ExtractCandidateInfo(BaseModel):
    skills: list
    tools: list
    industries: list
    years_experience: str
    seniority: str
    roles: list
    summary: str

class JobRequirements(BaseModel):
    job_id: int
    job_name: str
    company_name: str
    requirements: List[str]

@app.post("/api/analyze")
async def analyze_jobs(
    search_type: str = Form(...),
    lm_studio_api: str = Form(None),
    job_title: str = Form(""),
    company_name: str = Form(""),
    interval: int = Form(7),
    lim: int = Form(10),
    job_limit: int = Form(3),
    csv_file: UploadFile = File(None)
):
    app_mode = os.getenv("APP_MODE", "production").lower()

    if app_mode == "test":
        # --- TEST / MOCK MODE ---
        logging.info("Running analyze_jobs in TEST mode with mock responses.")
        
        common_skills_text = "Dummy Skills:\n- Python\n- SQL\n- FastAPI\n- React\n- Project Management\n- Technical Support\n- Troubleshooting\n- Communication\n- Linux\n- Docker"
        projects_text = "Dummy Projects:\n1. Build a local job analyzer web application using FastAPI and React.\n2. Design and query a PostgreSQL database to manage job listings.\n3. Create an automated report generator that outputs DOCX files."
        
        top_jobs = [
            {
                "job_id": "999",
                "job_name": "Mock Applied AI Engineer",
                "company_name": "Mock AI Corp",
                "matching_skills": ["Python", "FastAPI"],
                "missing_skills": ["React", "Docker"],
                "match_score": 90,
                "reasoning": "The candidate has strong Python and FastAPI experience, making them a great fit for building robust backend services, though they need to pick up React and Docker."
            },
            {
                "job_id": "998",
                "job_name": "Mock Technical Support Lead",
                "company_name": "Mock Tech Solutions",
                "matching_skills": ["Technical Support", "Troubleshooting", "Communication"],
                "missing_skills": ["Linux"],
                "match_score": 85,
                "reasoning": "Excellent match for support and troubleshooting skills, with minor gaps in advanced Linux admin tools."
            },
            {
                "job_id": "997",
                "job_name": "Mock Full-Stack Engineer",
                "company_name": "Mock Web Ventures",
                "matching_skills": ["Python", "FastAPI", "React"],
                "missing_skills": ["Docker", "Kubernetes"],
                "match_score": 80,
                "reasoning": "Good overlap with frontend and backend requirements, with modern framework experience."
            }
        ]
        
        adjustments = "### Resume Adjustments suggestions:\n1. **Highlight FastAPI/React Integration**: Emphasize hands-on experience in building full-stack applications.\n2. **Include Docker Projects**: List a containerized project to show cloud-native capability."
        
        pcm = ""
        for match in top_jobs[:job_limit]:
            pcm += f"\nJOB ID: {match['job_id']}\nJOB NAME: {match['job_name']}\nCOMPANY NAME: {match['company_name']}\nMATCH SCORE: {match['match_score']}%\nREASONING: {match['reasoning']}\n"
            
        filename = generate_job_report(
            job_title or "Test Job",
            company_name or "Test Company",
            common_skills_text,
            projects_text,
            pcm,
            adjustments
        )
        
        return {
            "job_title": job_title or "Test Job",
            "company_name": company_name or "Test Company",
            "common_skills": common_skills_text,
            "projects": projects_text,
            "matches": top_jobs[:job_limit],
            "adjustments": adjustments,
            "filename": filename
        }

    # --- PRODUCTION MODE ---
    gem_key = os.getenv("GEMINI_KEY")
    lm_port = os.getenv("LM_STUDIO_PORT", "1234")
    lm_model = os.getenv("LM_STUDIO_MODEL", "local-model")
    resume_file = os.getenv("RESUME")
    profile_file = os.getenv("PROFILE")

    # Override LM_STUDIO_API if provided via frontend
    lm_api = lm_studio_api if lm_studio_api else os.getenv("LM_STUDIO_API")

    if not gem_key:
        raise HTTPException(status_code=500, detail="GEMINI_KEY environment variable is not set.")
    if not lm_api:
        raise HTTPException(status_code=500, detail="LM_STUDIO_API is not provided via form or environment.")

    gem_conn = connect_gemini(gem_key)
    if gem_conn is None:
        raise HTTPException(status_code=500, detail="Unable to connect to Gemini API.")

    lm_conn = create_lm_connection(lm_api, int(lm_port), lm_model)
    langchain_connector = LangchainConnector(
        model_name=lm_conn.config.model_name,
        provider="lmstudio",
        base_url=lm_conn.base_url
    )

    try:
        resume = file_to_string(resume_file) if resume_file else ""
    except Exception as e:
        logging.error(f"Error loading resume file: {e}")
        resume = ""
        
    try:
        profile = file_to_string(profile_file) if profile_file else ""
    except Exception as e:
        logging.error(f"Error loading profile file: {e}")
        profile = ""

    jobs_list = []
    job_descriptions = []

    if search_type == "csv":
        if not csv_file:
            raise HTTPException(status_code=400, detail="CSV file is required for CSV search.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(await csv_file.read())
            tmp_path = tmp.name
        try:
            jobs_list, job_descriptions = load_jobs_from_csv(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error loading CSV file: {e}")
        finally:
            os.remove(tmp_path)
    elif search_type in ("job", "company"):
        if search_type == "job" and not job_title:
            raise HTTPException(status_code=400, detail="Job title is required for job search.")
        if search_type == "company" and not company_name:
            raise HTTPException(status_code=400, detail="Company name is required for company search.")
        
        # Parameters ordered correctly: job_title, company_name, type, limit, minusDays
        sql_query = create_sql_query(job_title, company_name, search_type, lim, interval)
        try:
            jobs_list, job_descriptions = pull_sql_data(sql_query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
    else:
        raise HTTPException(status_code=400, detail="Invalid search type.")

    if not jobs_list:
        raise HTTPException(status_code=404, detail="No jobs found matching the criteria.")

    common_skills_text = ""
    projects_text = ""

    if search_type in ("job", "csv") and job_descriptions:
        gem_skills_query = f'''
        The following is a list of job descriptions from similar jobs. Please return the following in Markdown format:
        - Top 10 responsibilities in the job description, from most frequent to least frequent
        - Top 10 skills in the job description, from most frequent to least frequent
        - Top 10 requirements in the job description, from most frequent to least frequent
        - Any certifications that commonly appear

        Ignore any industry specific experience, certifications, etc.

        job_descriptions: {'\n'.join(job_descriptions[:20])}
        ''' 
        try:
            common_skills_response = gem_conn.models.generate_content(
                model="gemini-3-flash-preview",
                contents=gem_skills_query
            )
            common_skills_text = common_skills_response.text or ""

            gem_projects_query = f'''
            The following is a list of top responsibilities for a specific job type, top skills for this job type, top requirements for this job type, and any certifications that are common for this job type. Return a list of projects you would suggest for someone trying to get into this role
            
            # Response of responsibilities, skills, requirements, and certifications
            {common_skills_text}
            '''
            projects_response = gem_conn.models.generate_content(
                model="gemini-3-flash-preview",
                contents=gem_projects_query
            )
            projects_text = projects_response.text or ""
        except Exception as e:
            logging.error(f"Gemini API error: {e}")

    templates = {
        "template_1": PromptTemplate(
            input_variables=["jid","jt","jc","jd"],
            template="""Provided is a job description. Please convert this into a list of responsibilities and job requirements for the position.

            Provide your response ONLY as valid JSON with NO markdown formatting (no ```json``` blocks). Use the following structure exactly:
            {{
                "job_id": <integer>,
                "job_name": <string>,
                "company_name": <string>,
                "requirements": [<string>,<string>,...]
            }}
        
            JOB ID: {jid}
            JOB TITLE: {jt}
            JOB COMPANY: {jc}
            JOB DESCRIPTION: {jd}
"""
        ),
        "template_2": PromptTemplate(
            input_variables=["resume"],
            template="""You are extracting structured candidate information.

ONLY use information explicitly stated in the resume or user profile.

Do NOT infer technologies, industries, or skills unless directly mentioned.

RESUME:
{resume}

Return JSON only.

{{
  "skills": [],
  "tools": [],
  "industries": [],
  "years_experience": "",
  "seniority": "",
  "roles": [],
  "summary": ""
}}
"""
        ),
        "template_3": PromptTemplate(
            input_variables=["candidate_json","profile","job_json"],
            template="""You are evaluating candidate fit for ONE job.

CANDIDATE SKILLS:
{candidate_json}
{profile}

JOB:
{job_json}

Rules:
- Only use evidence from CANDIDATE PROFILE when describing candidate skills.
- Soft skills can be inferred from the experience the user has and the work they've done.
- If the user has experience in a similar application, consider the experience a 
transferrable or equivalent skill, not the same as the specific program, but could easily 
be learned since the user is already experienced with similar applications
- If there is no evidence of a requirement or a similar skills or experience in the candidate profile or resume, state it as a gap.

Return JSON only.

{{
  "job_id": "",
  "job_name": "",
  "company_name": "",
  "requirements": [],
  "matching_skills": [],
  "missing_skills": [],
  "match_score": int(0-100),
  "reasoning": ""
}}
"""
        ),
        "template_4": PromptTemplate(
            input_variables=["top_matches_context","resume","profile"],
            template="""Provided is the top 3 job requirements and responsibilities, and the user's resume and user profile. For each job, make suggestions on what 
    adjustments should be made to the user's resume in order to better fit the job. You can pull from the User's profile in order to suggest specific skills and experience to
    focus on over information currently in the resume
    
    Include which job it is with what company and what the job ID is.

    TOP MATCHING JOBS REQUIREMENTS:
    [Top_Matches]
    {top_matches_context}
    [/Top_Matches]

    User's Resume:
    [Resume]
    {resume}
    [/Resume]

    User's Profile:
    [User_Profile]
    {profile}
    [/User_Profile]
"""
        )
    }

    chain_1 = langchain_connector.create_json_chain(templates["template_1"].template)
    chain_2 = langchain_connector.create_json_chain(templates["template_2"].template)
    chain_3 = langchain_connector.create_json_chain(templates["template_3"].template)
    chain_4 = langchain_connector.create_simple_chain(templates["template_4"].template)

    new_job_list = []
    for job in jobs_list:   
        template_1_output = await invoke_with_retry(
            chain_1,
            {
                "jid": job['id'],
                "jt": job['job_name'],
                "jc": job['company_name'],
                "jd": job['job_summary'],
            },
            lambda x: isinstance(x, dict) and 'requirements' in x
        )
        validated_job = JobRequirements(**template_1_output)
        new_job_list.append({
            'job_id': str(validated_job.job_id),
            'job_name': validated_job.job_name,
            'company_name': validated_job.company_name,
            'requirements': validated_job.requirements
        })

    try:
        candidate_info = await invoke_with_retry(
            chain_2,
            {"resume": resume},
            lambda x: isinstance(x, dict) and 'skills' in x and 'summary' in x
        )
        validated_candidate_info = ExtractCandidateInfo(**candidate_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting candidate info: {e}")

    ranking_analysis = []
    for job in new_job_list:
        template_3_output = await invoke_with_retry(
            chain_3,
            {
                "candidate_json": candidate_info,
                "profile": profile,
                "job_json": job
            },
            lambda x: isinstance(x, dict) and 'match_score' in x
        )
        validated_matches = JobFit(**template_3_output)
        ranking_analysis.append(template_3_output)
    
    top_jobs = sorted(ranking_analysis, key=lambda x: x['match_score'], reverse=True)[:job_limit]

    resume_suggestions = await invoke_with_retry(
        chain_4,
        {
            "top_matches_context": top_jobs,
            "resume": resume,
            "profile": profile
        },
        lambda x: isinstance(x, str) and len(x) > 0
    )

    pcm = ""
    for match in top_jobs:
        pcm += f"\nJOB ID: {match['job_id']}\nJOB NAME: {match['job_name']}\nCOMPANY NAME: {match['company_name']}\nMATCH SCORE: {match['match_score']}%\nREASONING: {match['reasoning']}\n"
    
    adjustments = f"{resume_suggestions}"

    filename = generate_job_report(job_title, company_name, common_skills_text, projects_text, pcm, adjustments)

    return {
        "job_title": job_title,
        "company_name": company_name,
        "common_skills": common_skills_text,
        "projects": projects_text,
        "matches": top_jobs,
        "adjustments": adjustments,
        "filename": filename
    }

@app.post("/api/generate_resume")
async def generate_resume(
    job_source: str = Form("file"),
    job_id: str = Form(None),
    lm_studio_api: str = Form(None),
    job_desc_file: UploadFile = File(None),
    profile_file: UploadFile = File(None),
    output_filename: str = Form("generated_resume")
):
    app_mode = os.getenv("APP_MODE", "production").lower()
    
    if app_mode == "test":
        logging.info("Running generate_resume in TEST mode.")
        import asyncio
        await asyncio.sleep(2)
        md_text = f"# Test Resume\n\nThis is a mock generated resume. Source: {job_source}, Job ID: {job_id}"
        os.makedirs("output", exist_ok=True)
        if not output_filename.endswith(".docx"):
            output_filename += ".docx"
        with open(os.path.join("output", output_filename), "w") as f:
            f.write(md_text) # just write text for mock docx
        return {
            "markdown": md_text,
            "filename": output_filename,
            "comparison": f"### Mock Comparison\nFit rating for Job ID {job_id if job_id else 'file'}: 95/100"
        }

    gem_key = os.getenv("GEMINI_KEY")
    lm_port = os.getenv("LM_STUDIO_PORT", "1234")
    lm_model = os.getenv("LM_STUDIO_MODEL", "local-model")
    lm_api = lm_studio_api if lm_studio_api else os.getenv("LM_STUDIO_API")

    if not gem_key:
        raise HTTPException(status_code=500, detail="GEMINI_KEY environment variable is not set.")
    if not lm_api:
        raise HTTPException(status_code=500, detail="LM_STUDIO_API is not provided via form or environment.")

    # Read job description based on job_source
    job_desc = ""
    if job_source == "sql":
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required when job_source is 'sql'")
        if not str(job_id).strip().isdigit():
            raise HTTPException(status_code=400, detail="Invalid job_id format. Must be numeric.")
        
        sql_query = f"SELECT job_summary FROM job WHERE id = {job_id};"
        try:
            results = execute_query_with_env_vars(sql_query)
            rows = [row for row in results]
            if not rows or 'job_summary' not in rows[0] or not rows[0]['job_summary']:
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found or has no summary in database.")
            job_desc = rows[0]['job_summary']
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Database error when fetching job: {e}")
    else:
        if not job_desc_file or not job_desc_file.filename:
            raise HTTPException(status_code=400, detail="Job description file is required when job_source is 'file'")
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(job_desc_file.filename)[1]) as tmp:
                tmp.write(await job_desc_file.read())
                tmp_job_path = tmp.name
            job_desc = file_to_string(tmp_job_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading job description file: {e}")
        finally:
            if 'tmp_job_path' in locals(): os.remove(tmp_job_path)

    # Read uploaded profile or fallback to .env PROFILE
    profile = ""
    if profile_file and profile_file.filename:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(profile_file.filename)[1]) as tmp:
                tmp.write(await profile_file.read())
                tmp_profile_path = tmp.name
            profile = file_to_string(tmp_profile_path)
        except Exception as e:
            logging.error(f"Error reading uploaded profile file: {e}")
        finally:
            if 'tmp_profile_path' in locals(): os.remove(tmp_profile_path)
    else:
        profile_env_path = os.getenv("PROFILE")
        if profile_env_path:
            try:
                profile = file_to_string(profile_env_path)
            except Exception as e:
                logging.error(f"Error reading profile from .env path: {e}")

    try:
        final_markdown, docx_filename, comparison_response = generate_resume_workflow(
            job_desc=job_desc,
            profile=profile,
            output_filename=output_filename,
            lm_api=lm_api,
            lm_port=int(lm_port),
            lm_model=lm_model,
            gem_key=gem_key
        )
        return {
            "markdown": final_markdown,
            "filename": docx_filename,
            "comparison": comparison_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating resume: {e}")

@app.get("/api/download/{filename}")
async def download_report(filename: str):
    file_path = os.path.join("output", filename)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
