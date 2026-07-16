import logging
from typing import List
from pydantic import BaseModel, Field
from app.prompts import TEMPLATE_1, TEMPLATE_2, TEMPLATE_3, TEMPLATE_4
from app.langchain_caller import LangchainConnector

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

async def invoke_with_retry(chain, inputs, validator, max_retries=3):
    """Invokes a LangChain chain with retry and validation logic."""
    for attempt in range(max_retries):
        try:
            output = await chain.ainvoke(inputs)
            if validator(output):
                return output
            else:
                logging.warning(f"  Validation failed on attempt {attempt + 1}")
        except Exception as e:
            logging.error(f"  Error on attempt {attempt + 1}: {e}")
    raise Exception(f"Failed after {max_retries} attempts")

async def run_candidate_job_fit(
    jobs_list: List[dict],
    langchain_connector: LangchainConnector,
    profile: str,
    job_limit: int
) -> tuple:
    """
    Executes the multi-step Langchain logic to analyze fit of candidate profile
    against a list of jobs.
    
    Returns:
        tuple: (top_jobs, resume_suggestions)
    """
    chain_1 = langchain_connector.create_json_chain(TEMPLATE_1.template)
    chain_2 = langchain_connector.create_json_chain(TEMPLATE_2.template)
    chain_3 = langchain_connector.create_json_chain(TEMPLATE_3.template)
    chain_4 = langchain_connector.create_simple_chain(TEMPLATE_4.template)

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

    candidate_info = await invoke_with_retry(
        chain_2,
        {"resume": profile},
        lambda x: isinstance(x, dict) and 'skills' in x and 'summary' in x
    )
    # Validate the data matches ExtractCandidateInfo structure
    _ = ExtractCandidateInfo(**candidate_info)

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
        # Validate data matches JobFit structure
        _ = JobFit(**template_3_output)
        ranking_analysis.append(template_3_output)
    
    top_jobs = sorted(ranking_analysis, key=lambda x: x['match_score'], reverse=True)[:job_limit]

    resume_suggestions = await invoke_with_retry(
        chain_4,
        {
            "top_matches_context": top_jobs,
            "resume": profile,  # Strictly candidate profile content
            "profile": profile
        },
        lambda x: isinstance(x, str) and len(x) > 0
    )

    return top_jobs, resume_suggestions
