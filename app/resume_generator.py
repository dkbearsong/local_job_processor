import os
import json
import logging
from typing import Dict, Any, List
import markdown
from docx import Document
from htmldocx import HtmlToDocx
from langchain_core.prompts import PromptTemplate

# Helper modules
from app.logger import log_debug_prompt, DEBUG_PROMPTS
from app.profile_verifier import verify_content_against_profile
from app.resume_formatter import format_resume_docx
from app.lm_connector import create_lmstudio_connector, create_gemini_langchain_connector

# Setup prompts
RESUME_GENERATION_STEPS = [
    {
        "step_name": "keyword_extractor",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Your goal is to extract the 15 most critical keywords and key phrases from a Job Description to ensure a candidate's profile matches the core requirements.\n\n**Analytical Framework:**\n\n- **Weighting:** Assign high priority to technical skills, domain expertise, specific tools/technologies, and specialized processes.\n- **Filtering:** Explicitly ignore \"soft skill\" clichés (e.g., \"self-starter,\" \"detail-oriented\") and generic corporate jargon unless they are specific to a niche industry requirement.\n- **Contextual Extraction:** Identify multi-word phrases that function as a single concept (e.g., \"Full Stack Development\" instead of just \"Full\" and \"Stack\").\n\n**Constraint Checklist:**\n\n1. Identify exactly 15 items.\n2. If the job description is short, select the most impactful terms available.\n\nJob Description:\n{job_desc}",
        "output_format": "json",
        "output_structure": "{\"keywords\": [str]}"
    },
    {
        "step_name": "job_pain_points",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Take the following job description and identify what pain points the company is having and identify what a top performer would bring to solve those paint points.\n\n**Strict Output Format:** exclude any introductory analysis or explanations of your work. Your response should consist of two sections, the Pain Points and the solutions a Top Performer will bring. Within each of these sections break it down into the points or proposed solutions and the explanation as to why.\n\nJob Description:\n{job_desc}",
        "output_format": "markdown",
        "output_structure": ""
    },
    {
        "step_name": "resume_skills_writeup",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Take the following job description, skills section from a user's profile, and job pain points. Write a skills segment from a resume that demonstrates the user can address the pain points using the provided skills section. Exclude points that do not demonstrate competency at solving these pain points and do not show up in the job description, either directly or implied.\n\nThe skills section should contain a comma separated list of skills grouped together by category, with the category title in bold followed by a colon. Example format: `**Category Name:** Skill 1, Skill 2`. DO NOT include bullet points for skills. You MAY add a colon after the category title even if it wasn't in the original profile.\n\n**USE ONLY THE EXACT WORDS PROVIDED IN THE PROFILE DOC. DO NOT REWRITE THE BULLET POINTS**\n\nJob Description:\n{job_desc}\n\nSkills Profile:\n{skills}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": ""
    },
    {
        "step_name": "resume_projects_writeup",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Take the following job description, projects section from a user's profile, and job pain points. Write a projects segment from a resume that demonstrates the user can address the pain points using the provided projects section. Exclude projects and points that do not demonstrate competency at solving these pain points.\n\nMake sure to include the project hyperlink if it is available in the profile.\n\n**USE ONLY THE EXACT WORDS PROVIDED IN THE PROFILE DOC. DO NOT REWRITE THE BULLET POINTS**\n\nJob Description:\n{job_desc}\n\nProjects Profile:\n{projects}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": "",
        "verify_against_profile": True
    },
    {
        "step_name": "resume_experience_writeup",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Take the following job description, experience section from a user's profile, and job pain points. Write an experience segment from a resume that demonstrates the user can address the pain points using the provided experience section. Exclude points that do not demonstrate competency at solving these pain points.\n\n**USE ONLY THE EXACT WORDS PROVIDED IN THE PROFILE DOC. DO NOT REWRITE THE BULLET POINTS**\n\nJob Description:\n{job_desc}\n\nExperience Profile:\n{experience}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": "",
        "verify_against_profile": True
    },
    {
        "step_name": "resume_summary_writeup",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Attached is a job description, a user profile, and pain points from the job description with suggested solutions. Write a three-sentence summary in a **telegraphic writing style** (stripping unnecessary verbs and filler words) that accomplishes the following:\n\n1. **Establish Relevance:** Immediately connect the user's core identity and experience to the specific role, avoiding generic statements.\n2. **Highlight Tech & Fit:** Clearly state the user's tech stack related to this job and how their background aligns with the company's needs.\n3. **Prove Impact:** Include **two notable achievements backed by specific metrics** that demonstrate how the user can directly solve the company's identified pain points.\n\nThe summary must prioritize **quantifiable impact** over duty lists, ensuring every word drives home the candidate's value proposition, and it should focus on demonstrating awareness of team's pain points and how the candidate will fix those pain. points.\n\nAvoid using common cliche phrases, terms, and corporate jargon such as the following\n\ndelve, leverage (as a verb), synergy, comprehensive, robust, dynamic, innovative, cutting-edge, meticulous, nuanced, pivotal, realm, tapestry, landscape, holistic, seamless, game-changer, groundbreaking, transformative, unprecedented, best-in-class, paradigm shift, at the intersection of, bridge the gap, consistently, seamlessly, effectively\n\nAnd do not use the following terms without including some evidence in the metrics section to demonstrate it: results-oriented, team player, hard worker, self-starter, detail-oriented, passionate, strategic thinker, expert\n\n-----\nExample Summaries\n-----\n\nDetail-oriented and data-driven Digital Marketer seeking to increase qualified leads and brand awareness for ABC Tech. Proven track record of growing social media engagement by over 40% and managing a monthly ad budget of $50K. Skilled in SEO/SEM strategies and marketing automation platforms to drive measurable results for your growth-focused team.\n\nAccomplished restaurant manager transitioning to corporate project management. Leverages exceptional leadership, budget management and operational efficiency skills honed over 7 years in the hospitality industry. Successfully managed teams of 20+, consistently controlled a $500k+ annual budget and improved customer service ratings by 25%. Eager to apply a proven track record of people and process management to a new challenge.\n\nJob Description:\n{job_desc}\n\nUser Profile:\n{user_profile_str}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": ""
    },
    {
        "step_name": "resume_writeup",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Take the following resume summary, experience section, skills section, projects section, user contact information, and education section and write a resume no longer than 2 pages from this. Use the attached job description to base how the resume should be organized, and ensure that the top 1/3 of the resume would make you want to follow up with the individual if you were a recruiter. There will also be a list of pain points that the company is likely trying to address with this hire, use this as a reference point to what this resume should be trying to solve.\n\nInclude only the following sections in this order:\n- Contact header\n- Summary\n- Experience\n- Projects\n- Skills\n- Education\n\nFor the projects section, include no more than four projects, preferrably 3 unless additional projects would be helpful for a career transition\n\n**FORMATTING REQUIREMENTS (CRITICAL):**\n- Use proper markdown headers for each section: `## Summary`, `## Experience`, `## Projects`, `## Skills`, `## Education`\n- Use `###` for job titles/company names under Experience\n- Use `###` for project titles, and make sure to include the project hyperlink if it is available in the profile.\n- Use `- ` for bullet points (each bullet on its own line)\n- Separate sections with exactly ONE blank line\n- Do NOT use bold text (`**`) as section headers - use `##` headers instead\n- Preserve all line breaks exactly as shown in the source material\n\n**USE ONLY THE EXACT WORDS PROVIDED IN THE USER PROMPT. DO NOT REWRITE THE BULLET POINTS**\n\n================================================================================\n\nSummary:\n{resume_summary_writeup}\n\nExperience:\n{resume_experience_writeup}\n\nSkills:\n{resume_skills_writeup}\n\nProjects:\n{resume_projects_writeup}\n\nContact Information:\n{contact_info}\n\nEducation:\n{education}\n\nJob Description:\n{job_desc}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": ""
    },
    {
        "step_name": "resume_keyword_injection",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Your task is to seamlessly integrate a provided list of target keywords and key phrases into a candidate's existing resume.\n\nYour primary directive is to maximize ATS (Applicant Tracking System) compatibility while maintaining absolute factual integrity and preserving the candidate's original voice, structure, and experience.\n\n**NOTE**: Do not include any writeup before the resume or explanation about the work.\n---\n\n## Strict Optimization Criteria\n\n### 1. The Direct-Equivalent Rule (No Factual Inflation)\n* **Only** inject a target keyword or phrase if there is already an existing, direct equivalent or synonym in the original resume.\n* Do **not** upgrade, exaggerate, or invent skills, tools, or responsibilities. For example, if the resume says \"managed projects\" and the keyword is \"Enterprise Agile Program Management,\" do *not* use it unless the original text explicitly supports that level of seniority and methodology.\n* If a target keyword has no logical, factual equivalent in the original text, **skip it entirely**.\n\n### 2. Structural & Linguistic Preservation\n* Retain the original layout, headings, bullet points, and chronological order of the resume.\n* Maintain the original phrasing and words as closely as possible.\n* Only make minor, highly contextual adjustments (such as changing a verb tense or swapping a generic noun for a specific target keyword) necessary to integrate the phrase cleanly. The sentence structure should feel natural and unforced.\n\n### 3. Zero-Hallucination Guardrail\n* You are strictly forbidden from adding new metrics, scope, technologies, company details, or outcomes that are not explicitly present in the source text.\n* Do not rewrite entire paragraphs. Focus on surgical, word-level or phrase-level replacements.\n\n---\n\n## Output Requirements\n\nProvide the optimized resume in its entirety.\n\nKeywords:\n{keywords}\n\nResume:\n{resume_writeup}",
        "output_format": "markdown",
        "output_structure": ""
    },
    {
        "step_name": "review_keyword_injection",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "You will be provided with an original resume and a modified resume where keywords were injected to better align the resume with a job description. Compare the two resumes summary, experience, skills, projects, contact information, and education sections. Verify that the information provided has not changed in terms of original intent and that no facts about this user has been hallucinated and provide a rating out of 100 for how similar the two are in fit.\n\nIf anything does not line up between the two resumes, note what specifically was wrong and what needs to be done to fix it so that it is in line with the original intent while using the attached keywords and key phrases that were provided to be injected into the resume. Then rewrite the resume with the suggested changes.\n\n**CRITERIA**\n\n- If any changes need to be made, ONLY provide a list of the incorrect information in the last resume and a list of what changes need to be made in order to correct the issue, followed by a corrected resume\n\nOriginal Resume:\n{resume_writeup}\n\nModified Resume:\n{resume_keyword_injection}",
        "output_format": "json",
        "output_structure": "{\"fit_score\":int,\"issues\":[{\"problem\":str, \"solution\":str}], \"resume\":str}"
    },
    {
        "step_name": "job_and_resume_comparison",
        "llm": "lmstudio",
        "model": "local-model",
        "prompt": "Attached is my resume, a job description, and a list of job pain points. Compare my resume against the job description and suggestions. Think as if you are the hiring manager. If you were scanning through this resume, does the top 1/3 of the resume capture your attention in the 8 seconds you might scan it? Does it scream that I am the person who can solve your problems? Does it say I'm a top performer who brings the right skills and qualifications to solve these problems? Let me know yes or no, give a numerical grading, and answer and why or why not. Then provide suggestions on how to improve this fit while maintaining the original information that was conveyed in the resume. If additional experience or bullet points should be added that are not included in the resume, specify to add this information and what I should look for in experience or skills to demonstrate fit.\n\nResume:\n{resume}\n\nJob Description:\n{job_desc}\n\nPain Points:\n{job_pain_points}",
        "output_format": "markdown",
        "output_structure": ""
    }
]


def parse_profile_to_sections(profile_text: str) -> Dict[str, str]:
    """
    Parse a markdown profile into sections based on # headers.
    Content before the first # header is treated as "Contact Info".
    Returns a dict with section names as keys and content as values.
    """
    sections = {}
    current_section = None
    current_content = []
    before_first_header = []

    for line in profile_text.split('\n'):
        if line.startswith('# '):
            if current_section is None and before_first_header:
                sections["Contact Info"] = '\n'.join(before_first_header).strip()
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[2:].strip()
            current_content = []
        else:
            if current_section is None:
                before_first_header.append(line)
            else:
                current_content.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def generate_resume_workflow(
    job_desc: str,
    profile: str,
    folder_path: str,
    company_name: str,
    job_name: str,
    lm_api: str,
    lm_port: int,
    lm_model: str,
    gem_key: str
) -> tuple:
    """
    Runs the sequential prompts to generate a tailored resume.
    """
    user_profile = parse_profile_to_sections(profile) if profile else {}

    context: Dict[str, Any] = {
        "job_desc": job_desc,
        "user_profile": user_profile,
        "user_profile_str": json.dumps(user_profile, indent=2),
        "contact_info": user_profile.get("Contact Info", ""),
        "skills": user_profile.get("Skills", ""),
        "experience": user_profile.get("Experience", ""),
        "projects": user_profile.get("Projects", ""),
        "education": user_profile.get("Education", ""),
    }

    connectors = {}
    
    # Centralized connection setup
    if lm_api:
        connectors["lmstudio"] = create_lmstudio_connector(lm_api, lm_port, lm_model)
    
    if gem_key:
        connectors["gemini"] = create_gemini_langchain_connector(gem_key)

    # Iterate over steps
    for step in RESUME_GENERATION_STEPS:
        step_name = step["step_name"]
        llm_provider = step["llm"]
        model = step["model"]
        prompt_template = step["prompt"]
        output_format = step["output_format"]
        output_structure = step.get("output_structure", "")

        logging.info(f"Running step: {step_name} using {llm_provider} ({model})")

        if llm_provider not in connectors:
            raise ValueError(f"Connector for provider '{llm_provider}' is not configured.")

        connector = connectors[llm_provider]
        connector.set_model(model_name=model)

        verify_enabled = step.get("verify_against_profile", False)
        max_attempts = 6
        current_attempt = 1
        mismatches = []
        current_prompt_template = prompt_template

        while current_attempt <= max_attempts:
            if current_attempt > 1:
                logging.info(f"Retrying step: {step_name} (Attempt {current_attempt}/{max_attempts}) due to {len(mismatches)} mismatches.")
                mismatch_notes = "\n".join([f"- {m}" for m in mismatches])
                current_prompt_template = (
                    f"NOTE TO AI: The data in the response contained information not found in the user profile.\n"
                    f"Specifically, the following information did not match:\n"
                    f"{mismatch_notes}\n\n"
                    f"Please repeat the last task. Ensure that you use ONLY the exact words provided in the user profile. DO NOT rewrite, modify, or add any information.\n\n"
                    f"Last task instructions:\n"
                    f"{prompt_template}"
                )

            # Centralized chain initialization and try/except execution block
            if output_format == "json":
                full_prompt = current_prompt_template
                if output_structure:
                    escaped_structure = output_structure.replace('{', '{{').replace('}', '}}')
                    full_prompt += f"\n\nRespond ONLY with valid JSON using the following structure: {escaped_structure}"
                
                chain = connector.create_json_chain(full_prompt)
                prompt_to_log = full_prompt
                fallback_val = {}
            else:
                chain = connector.create_simple_chain(current_prompt_template)
                prompt_to_log = current_prompt_template
                fallback_val = ""

            try:
                rendered = ""
                if DEBUG_PROMPTS:
                    rendered = PromptTemplate.from_template(prompt_to_log).format(**context)
                response = chain.invoke(context)
                context[step_name] = response
                if DEBUG_PROMPTS:
                    log_debug_prompt(step_name, rendered, response)
            except Exception as e:
                logging.error(f"Error in step {step_name} (Attempt {current_attempt}/{max_attempts}): {e}")
                if current_attempt == max_attempts:
                    raise
                context[step_name] = fallback_val
                current_attempt += 1
                continue

            if not verify_enabled:
                break

            response_str = json.dumps(response) if isinstance(response, dict) else str(response)
            mismatches = verify_content_against_profile(response_str, profile, step_name)

            if not mismatches:
                logging.info(f"Verification successful for step {step_name} on attempt {current_attempt}.")
                break
            else:
                logging.warning(f"Verification failed for step {step_name} on attempt {current_attempt} with {len(mismatches)} mismatches.")
                current_attempt += 1
                if current_attempt > max_attempts:
                    error_msg = f"Failed to generate valid content for step '{step_name}' after 5 retries. The following information from the response could not be verified in the user profile:\n" + "\n".join([f"- {m}" for m in mismatches])
                    logging.error(error_msg)
                    raise ValueError(error_msg)

        # Post-processing for specific steps
        if step_name == "keyword_extractor":
            try:
                if isinstance(context[step_name], dict):
                    kw_list = context[step_name].get("keywords", [])
                else:
                    kw_data = json.loads(context[step_name]) if isinstance(context[step_name], str) else {}
                    kw_list = kw_data.get("keywords", [])
                context["keywords"] = json.dumps(kw_list, indent=2)
            except Exception as e:
                logging.error(f"Error extracting keywords from {step_name}: {e}")
                context["keywords"] = "[]"

        if step_name == "review_keyword_injection":
            try:
                if isinstance(context[step_name], dict):
                    fit_score = context[step_name].get("fit_score", 0)
                    reviewed_resume = context[step_name].get("resume", "")
                else:
                    review_data = json.loads(context[step_name]) if isinstance(context[step_name], str) else {}
                    fit_score = review_data.get("fit_score", 0)
                    reviewed_resume = review_data.get("resume", "")

                if fit_score >= 72:
                    context["resume"] = context.get("resume_writeup", "")
                    logging.info(f"fit_score={fit_score} >= 72, using original resume_writeup")
                else:
                    context["resume"] = reviewed_resume
                    logging.info(f"fit_score={fit_score} < 72, using reviewed resume from review_keyword_injection")
            except Exception as e:
                logging.error(f"Error processing review_keyword_injection: {e}")
                context["resume"] = context.get("resume_writeup", "")

    final_markdown = context.get("resume", "")
    comparison_response = context.get("job_and_resume_comparison", "")

    os.makedirs(folder_path, exist_ok=True)
    file_prefix = f"{job_name} - {company_name}"
    
    # Write Final Report
    report_filename = f"{file_prefix} - Final Report.md"
    report_path = os.path.join(folder_path, report_filename)
    with open(report_path, "w") as f:
        f.write(comparison_response)
        
    # Write Job Pain Points
    pain_points_filename = f"{file_prefix} - Job Pain Points.md"
    pain_points_path = os.path.join(folder_path, pain_points_filename)
    with open(pain_points_path, "w") as f:
        f.write(context.get("job_pain_points", ""))

    # Write Resume docx
    docx_filename = f"{file_prefix} - Resume.docx"
    output_path = os.path.join(folder_path, docx_filename)
    
    html_content = markdown.markdown(final_markdown)
    
    document = Document()
    new_parser = HtmlToDocx()
    new_parser.add_html_to_document(html_content, document)
    document.save(output_path)
    
    # Format the generated docx
    # NOTE: To customize the resume layout/formatting style, edit the rules in app/resume_formatter.py
    format_resume_docx(output_path)
    
    return final_markdown, docx_filename, comparison_response