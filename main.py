# Libraries
import csv
import os
import sys
from typing import List
import pypdf
from docx import Document
import google.genai as genai
from openai import OpenAI
from pydantic import BaseModel, Field
import asyncio
from langchain_core.prompts import PromptTemplate

# Modules
from app.logger import setup_logging, exception_handler
from app.postgres_ssh_connector import execute_query_with_env_vars
from app.report_generator import generate_job_report
from app.lm_connector import create_lm_connection
from app.langchain_caller import LangchainConnector

# Added for testing mode
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

def connect_lms(lm_api:str):
    """Builds a connection to a local install of LM Studio, taking in the API path as a variable and returns the client."""
    try:
        # LM Studio uses an OpenAI-compatible endpoint
        client = OpenAI(base_url=lm_api, api_key="lm-studio")
        return client
    except Exception as e:
        print(f"LM Studio connection error: {e}")
        return None
    
def create_sql_query(job_title: str, company_name: str, type:str, limit: int = 3, minusDays:int = 7, ):
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

    
def pull_sql_data(query:str):
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
        file_reader= Document(file_name)
        text = "\n".join([paragraph.text for paragraph in file_reader.paragraphs])
        return text
    elif file_name.lower().endswith(".txt"):
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read().strip()
    else:
        raise ValueError(f"Unsupported file format: {file_name}. Please provide a .pdf or .docx file.")


########################## AI Functions #########################################

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

######################## Main Function #################################

async def main():
    # Initialize Error Logging
    setup_logging("project_errors.log")

    # Set the global exception hook to catch unhandled crashes
    sys.excepthook = exception_handler

    # pull from env
    gem_key = os.getenv("GEMINI_KEY")
    lm_api = os.getenv("LM_STUDIO_API")
    lm_port = os.getenv("LM_STUDIO_PORT")
    lm_model = os.getenv("LM_STUDIO_MODEL")
    resume_file = os.getenv("RESUME")
    resume = file_to_string(resume_file)
    profile_file = os.getenv("PROFILE")
    profile = file_to_string(profile_file)
    app_mode = os.getenv("APP_MODE", "production") # Added to detect test mode

    # Check for required environment variables
    if app_mode != "test":
        if not gem_key:
            raise ValueError("GEMINI_KEY environment variable is not set.")
        if not lm_api:
            raise ValueError("LM_STUDIO_API environment variable is not set.")

    # Build connectors
    if app_mode != "test":
        gem_conn = connect_gemini(gem_key)
        if gem_conn is None:
            raise ConnectionError("Unable to connect to Gemini API with provided key.")
    else:
        gem_conn = None

    assert lm_api is not None, "LM_STUDIO_API environment variable is not set."
    assert lm_port is not None, "LM_STUDIO_PORT environment variable is not set."
    assert lm_model is not None, "LM_STUDIO_MODEL environment variable is not set."

    lm_conn = create_lm_connection(lm_api, int(lm_port), lm_model)
    # Initialize LangchainConnector to use LM Studio
    base_url = lm_conn.base_url
    print(f"Using LLM base_url: {base_url}")
    langchain_connector = LangchainConnector(
        model_name=lm_conn.config.model_name,
        provider="lmstudio",
        base_url=base_url
    )

    import logging
    logging.info(f"Project started in {app_mode} mode.")

    job_title = ""
    company_name = ""

    if app_mode == "test":
        # --- TEST MODE SETUP: JUMPING DIRECTLY TO STEP 1 ---
        print("Running in TEST MODE. Using dummy data and bypassing Gemini/SQL calls.")

        # 0. SQL Search
        job_title = 'Support Engineer'
        search_type = "job"
        sql_query = create_sql_query(job_title, company_name, search_type, 10)
        job_limit = 3
        
         # Execute SQL query using the SSH connector module
        try:
            jobs_list, job_descriptions = pull_sql_data(sql_query)
        except Exception as e:
            raise e
        
        # print(f"Jobs List: {jobs_list}\n\n")
        
        # 1. & 2. Set response for common_skills and projects
        common_skills_response = MockResponse(text="Dummy Skills: Python, SQL, Project Management")
        projects_response = MockResponse(text="Dummy Projects: Build a web scraper, Create a database schema")
        
        # Initialize minimal jobs_list so Step 1 loop works
        #jobs_list = [{
        #    'id': '999', 
        #    'job_name': 'Test Engineer', 
        #    'job_summary': 'Looking for someone with Python and SQL experience.'
        #}]
        
        # Prepare text variables used later in report generation
        common_skills_text = common_skills_response.text
        projects_text = projects_response.text
        # job_title = "Test Job"
    else:
        # --- PRODUCTION MODE: RUNNING ACTUAL LOGIC ---

        use_csv = input("Would you like to load job data from a CSV file instead of SQL? (y/n): ").strip().lower()
        if use_csv in ("y", "yes"):
            csv_path = input("Please provide the path to the CSV file: ").strip()
            try:
                jobs_list, job_descriptions = load_jobs_from_csv(csv_path)
            except Exception as e:
                raise ValueError(f"Error loading CSV file: {e}")
            print(f"Loaded {len(jobs_list)} jobs from CSV file.")
            search_type = "csv"
            job_limit = int(input("Please provide the count of top jobs to show: "))
        else:
            # Get job title or company name to search for and compare
            search_type = input("Please identify if you want to run a search by job or by company: ")
            while search_type not in ("job","company"):
                search_type = input("Invalid type. Please specify whether to search by job or by company: ")
            # Initialize variables - only one will be used based on search type
            if search_type == "job":
                job_title = input("Please provide the job title you would like to analyze job descriptions for: ")
            elif search_type == "company":
                company_name = input("Please provide the company name you would like to search for: ")

            interval = int(input("Please provide the number of days you would like to go back: "))
            lim = int(input("Please provide the amount of jobs with the title you would like to limit to: "))
            job_limit = int(input("Please provide the count of top jobs to show: "))

            sql_query = create_sql_query(job_title, company_name, search_type, interval, lim)

            # Execute SQL query using the SSH connector module
            try:
                jobs_list, job_descriptions = pull_sql_data(sql_query)
            except Exception as e:
                raise e
            
            print(f"Processing {len(jobs_list)} jobs...")

        if search_type in ("job"):
            gem_skills_query = f'''
            The following is a list of job descriptions from similar jobs. Please return the following in Markdown format:
            - Top 10 responsibilities in the job description, from most frequent to least frequent
            - Top 10 skills in the job description, from most frequent to least frequent
            - Top 10 requirements in the job description, from most frequent to least frequent
            - Any certifications that commonly appear

            Ignore any industry specific experience, certifications, etc.

            job_descriptions: {'\n'.join(job_descriptions)}
            ''' 

            assert gem_conn is not None, "Gemini connection required in production mode."
            common_skills_response = gem_conn.models.generate_content(
                model="gemini-3-flash-preview",
                contents=gem_skills_query
            )

            ### print(common_skills_response)

            # Run call to Gemini to get suggestions on what projects to build to demonstrate the skills
            gem_projects_query = f'''
            The following is a list of top responsibilities for a specific job type, top skills for this job type, top requirements for this job type, and any certifications that are common for this job type. Return a list of projects you would suggest for someone trying to get into this role
            
            # Response of responsibilities, skills, requirements, and certifications
            {common_skills_response.text}
            '''

            projects_response = gem_conn.models.generate_content(
                model="gemini-3-flash-preview",
                contents=gem_projects_query
            )

            # Write Gemini responses to report
            common_skills_text = common_skills_response.text or ""
            projects_text = projects_response.text or ""
        else:
            common_skills_text = ""
            projects_text = ""

    # Run local call to LM-Studio to compare resume and user profile to list of jobs and 
    # identify the top 3 jobs that would suggest targeting



    # Write LM-Studio responses to report

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

    # Step 0: define output structure
    # 1. Define the output structure
    class JobFit(BaseModel):
        job_id: str
        job_name: str
        company_name: str
        matching_skills: List[str]
        missing_skills: List[str]
        match_score: int = Field(description="Score from 0-100")
        reasoning: str = Field(description="Brief explanation of why this is a top match")

    class ExtractCandateInfo(BaseModel):
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

    # Create chains for each template
    chain_1 = langchain_connector.create_json_chain(templates["template_1"].template)
    chain_2 = langchain_connector.create_json_chain(templates["template_2"].template)
    chain_3 = langchain_connector.create_json_chain(templates["template_3"].template)
    chain_4 = langchain_connector.create_simple_chain(templates["template_4"].template)

    ## Step 1: loop over job descriptions with langchain call to convert into list of requirements and qualifications and tie back to job id and job name as new list of dicts
    new_job_list = []
    print("[1/5] Converting job description into list of requirements...")
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

        # Validate the output
        validated_job = JobRequirements(**template_1_output)

        print(f"Processing job: {validated_job.job_name} at {validated_job.company_name}")
        
        new_job_list.append({
            'job_id': str(validated_job.job_id),
            'job_name': validated_job.job_name,
            'company_name': validated_job.company_name,
            'requirements': validated_job.requirements
        })

    print(f"New Job List: {new_job_list}")

    ## Step 2: extract candidate information
    print("[2/5] Extracting candidate information...")
    try:
        candidate_info = await invoke_with_retry(
            chain_2,
            {
                "resume": resume
            },
            lambda x: isinstance(x, dict) and 'skills' in x and 'summary' in x
        )
        print(f"Raw Response: {candidate_info}")
        # Validate the response against our Pydantic model
        validated_candidate_info = ExtractCandateInfo(**candidate_info)
    except Exception as e:
        print(f"JSON Validation Error: {e}")
        # Fallback or retry logic could go here
        raise
    


    ## Step 3: Compare skills to job description
    print("[3/5] Comparing skills to job description...")
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

    ## Step 4: run single prompt with top 3 to make suggestions on how to adjust resume for better fit
    print("[4/5] Generating resume adjustment suggestions...")
    resume_suggestions = await invoke_with_retry(
        chain_4,
        {
            "top_matches_context": top_jobs,
            "resume": resume,
            "profile": profile
        },
        lambda x: isinstance(x, str) and len(x) > 0
    )

    ## Step 5: write report to docx showing details on top 3 jobs and suggestions on how to better fit them before applying
    print("[5/5] Generating final report...")
    # We format the LM Studio results into a string to append or pass to your docx generator
    pcm = ""
    for match in top_jobs:
        pcm += f"\nJOB ID: {match['job_id']}\nJOB NAME: {match['job_name']}\nCOMPANY NAME: {match['company_name']}\nMATCH SCORE: {match['match_score']}%\nREASONING: {match['reasoning']}\n"
    
    adjustments = f"{resume_suggestions}"

    # Append the findings to your existing report generation logic
    # (Assuming generate_job_report can be called again or handles appending)
    generate_job_report(job_title, company_name, common_skills_text, projects_text, pcm, adjustments)

if __name__ == "__main__":
    asyncio.run(main())

