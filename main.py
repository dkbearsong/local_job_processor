# Libraries
import csv
import os
import sys
from typing import List
import pypdf
from docx import Document
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import logging

# Modules
from app.logger import setup_logging, exception_handler
from app.postgres_ssh_connector import execute_query_with_env_vars
from app.report_generator import generate_job_report
from app.lm_connector import create_gemini_client, create_lmstudio_connector
from app.job_analyzer import run_candidate_job_fit, JobFit, JobRequirements
from app.prompts import GEM_SKILLS_QUERY, GEM_PROJECTS_QUERY
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

############################## Helper Functions ####################################

def load_llm_config(lm_studio_api_override: str | None = None) -> tuple:
    """Loads environment configuration and validates necessary credentials."""
    gem_key = os.getenv("GEMINI_KEY")
    lm_port = os.getenv("LM_STUDIO_PORT", "1234")
    lm_model = os.getenv("LM_STUDIO_MODEL", "local-model")
    lm_api = lm_studio_api_override if lm_studio_api_override else os.getenv("LM_STUDIO_API")

    if not gem_key:
        raise HTTPException(status_code=500, detail="GEMINI_KEY environment variable is not set.")
    if not lm_api:
        raise HTTPException(status_code=500, detail="LM_STUDIO_API is not provided via form or environment.")
        
    return gem_key, lm_api, int(lm_port), lm_model


async def get_user_profile(profile_file: UploadFile | None = None) -> str:
    """Standardized function to load the user profile from file upload or env path fallback."""
    profile = ""
    if profile_file and profile_file.filename:
        try:
            suffix = os.path.splitext(profile_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await profile_file.read())
                tmp_path = tmp.name
            profile = file_to_string(tmp_path)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        except Exception as e:
            logging.error(f"Error reading uploaded profile file: {e}")
    else:
        profile_env_path = os.getenv("PROFILE")
        if profile_env_path:
            try:
                profile = file_to_string(profile_env_path)
            except Exception as e:
                logging.error(f"Error reading profile from .env path: {e}")
    return profile


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


############################## API Endpoints ####################################

@app.post("/api/analyze")
async def analyze_jobs(
    search_type: str = Form(...),
    lm_studio_api: str = Form(None),
    job_title: str = Form(""),
    company_name: str = Form(""),
    interval: int = Form(7),
    lim: int = Form(10),
    job_limit: int = Form(3),
    csv_file: UploadFile = File(None),
    profile_file: UploadFile = File(None)
):
    gem_key, lm_api, lm_port, lm_model = load_llm_config(lm_studio_api)

    gem_client = create_gemini_client(gem_key)
    if gem_client is None:
        raise HTTPException(status_code=500, detail="Unable to connect to Gemini API.")

    lm_connector = create_lmstudio_connector(lm_api, lm_port, lm_model)

    # Standardized helper to pull profile
    profile = await get_user_profile(profile_file)

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
        formatted_gem_skills_query = GEM_SKILLS_QUERY.format(job_descriptions='\n'.join(job_descriptions[:20]))
        try:
            common_skills_response = gem_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=formatted_gem_skills_query
            )
            common_skills_text = common_skills_response.text or ""

            formatted_gem_projects_query = GEM_PROJECTS_QUERY.format(common_skills_text=common_skills_text)
            projects_response = gem_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=formatted_gem_projects_query
            )
            projects_text = projects_response.text or ""
        except Exception as e:
            logging.error(f"Gemini API error: {e}")

    try:
        top_jobs, resume_suggestions = await run_candidate_job_fit(
            jobs_list=jobs_list,
            langchain_connector=lm_connector,
            profile=profile,
            job_limit=job_limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during job fit analysis: {e}")

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
    folder_path: str = Form(...),
    company_name: str = Form(""),
    job_name: str = Form("")
):
    gem_key, lm_api, lm_port, lm_model = load_llm_config(lm_studio_api)

    # Read job description based on job_source
    job_desc = ""
    if job_source == "sql":
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required when job_source is 'sql'")
        if not str(job_id).strip().isdigit():
            raise HTTPException(status_code=400, detail="Invalid job_id format. Must be numeric.")
        
        sql_query = f"""
            SELECT j.job_summary, j.job_name, c.company_name 
            FROM job j 
            LEFT JOIN company c ON j.company_id = c.id 
            WHERE j.id = {job_id};
        """
        try:
            results = execute_query_with_env_vars(sql_query)
            rows = [row for row in results]
            if not rows or 'job_summary' not in rows[0] or not rows[0]['job_summary']:
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found or has no summary in database.")
            job_desc = rows[0]['job_summary']
            job_name = rows[0]['job_name'] or job_name
            company_name = rows[0]['company_name'] or company_name
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
            if 'tmp_job_path' in locals():
                try:
                    os.remove(tmp_job_path)
                except Exception:
                    pass

    # Read profile using the standardized function
    profile = await get_user_profile(profile_file)

    try:
        final_markdown, docx_filename, comparison_response = generate_resume_workflow(
            job_desc=job_desc,
            profile=profile,
            folder_path=folder_path,
            company_name=company_name,
            job_name=job_name,
            lm_api=lm_api,
            lm_port=int(lm_port),
            lm_model=lm_model,
            gem_key=gem_key
        )
        return {
            "markdown": final_markdown,
            "folderPath": folder_path,
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
