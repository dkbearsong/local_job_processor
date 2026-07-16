import os
from pydantic import BaseModel, Field
from google.genai import Client
from google.genai.types import GenerateContentConfig

# Define the output structure
class JobFit(BaseModel):
    job_id: str
    match_score: int = Field(description="Score from 0-100")
    reasoning: str = Field(description="Brief explanation of why this is a top match")

class TopJobsResponse(BaseModel):
    top_matches: list[JobFit]

client = Client(api_key=os.getenv("GEMINI_KEY"))

def get_top_3_jobs(resume_text: str, user_profile: str, jobs_list: list[dict]) -> TopJobsResponse:
    prompt = f"""
You are a job matching assistant. Given a resume, user profile, and a list of jobs, identify the top 3 best-matching jobs.

Resume:
{resume_text}

User Profile:
{user_profile}

Jobs:
{jobs_list}

Return the top 3 matches as a JSON object with a "top_matches" array, where each match has:
- job_id: the job's ID
- match_score: an integer from 0-100
- reasoning: a brief explanation of why this is a top match
"""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=GenerateContentConfig(response_mime_type="application/json")
    )
    
    text = response.text
    if text is None:
        raise ValueError("Gemini returned an empty response")
    return TopJobsResponse.model_validate_json(text)
