from langchain_core.prompts import PromptTemplate

GEM_SKILLS_QUERY = '''
The following is a list of job descriptions from similar jobs. Please return the following in Markdown format:
- Top 10 responsibilities in the job description, from most frequent to least frequent
- Top 10 skills in the job description, from most frequent to least frequent
- Top 10 requirements in the job description, from most frequent to least frequent
- Any certifications that commonly appear

Ignore any industry specific experience, certifications, etc.

job_descriptions: {job_descriptions}
'''

GEM_PROJECTS_QUERY = '''
The following is a list of top responsibilities for a specific job type, top skills for this job type, top requirements for this job type, and any certifications that are common for this job type. Return a list of projects you would suggest for someone trying to get into this role

# Response of responsibilities, skills, requirements, and certifications
{common_skills_text}
'''

TEMPLATE_1 = PromptTemplate(
    input_variables=["jid", "jt", "jc", "jd"],
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
)

TEMPLATE_2 = PromptTemplate(
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
)

TEMPLATE_3 = PromptTemplate(
    input_variables=["candidate_json", "profile", "job_json"],
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
)

TEMPLATE_4 = PromptTemplate(
    input_variables=["top_matches_context", "resume", "profile"],
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
