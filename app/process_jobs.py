import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List

# 1. Define the output structure
class JobFit(BaseModel):
    job_id: str
    match_score: int = Field(description="Score from 0-100")
    reasoning: str = Field(description="Brief explanation of why this is a top match")

class TopJobsResponse(BaseModel):
    top_matches: List[JobFit]

# 2. Configure Gemini (using Gemini 3 Flash for speed/context)
genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel("gemini-3-flash")

def get_top_3_jobs(resume_text, user_profile, jobs_list):
    
    
    # Use the 'response_mime_type' to enforce JSON
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    return TopJobsResponse.model_validate_json(response.text)