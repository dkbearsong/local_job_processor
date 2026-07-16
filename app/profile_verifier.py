import json
from typing import List

def normalize_text_alphanumeric(text: str) -> str:
    """Normalize text by converting to lowercase and keeping only alphanumeric characters."""
    return "".join(c.lower() for c in text if c.isalnum())


def is_generic_category(text: str) -> bool:
    """Check if the text is a generic skill category header."""
    category_keywords = {
        "ai", "automation", "software", "engineering", "systems", "devops",
        "problem", "solving", "governance", "programming", "languages",
        "tools", "databases", "frameworks", "methodologies", "cloud",
        "services", "other", "llm", "support", "escalation", "productivity",
        "certifications", "api", "integrations", "web", "development",
        "operating", "version", "control", "processes", "operations",
        "integration", "management", "networking", "infrastructure", "sop",
        "professional", "technical", "core", "applications", "methodology",
        "skills", "collaboration", "database", "security", "administration",
        "incident", "handling", "training", "analysis", "communication"
    }
    
    words = [w.strip().lower() for w in text.split() if w.strip()]
    if not words:
        return False
        
    filtered_words = [w for w in words if w not in ("&", "and", "or", "/", "-", "to", "for", "with")]
    if not filtered_words:
        return False
        
    return all(w in category_keywords for w in filtered_words)


def verify_content_against_profile(ai_response: str, original_profile: str, step_name: str) -> List[str]:
    """
    Verify that all of the candidate-specific content in the AI response
    can be found in the original user profile.
    Returns a list of mismatched items/lines.
    """
    if not original_profile:
        return []

    normalized_profile = normalize_text_alphanumeric(original_profile)
    lines = ai_response.split('\n')
    mismatches = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        if line_stripped.startswith('#'):
            continue

        cleaned = line_stripped
        while cleaned and (cleaned[0] in ('-', '*', '+', '>', ' ', '\t') or cleaned[0].isdigit() or (cleaned[0] == '.' and len(cleaned) > 1 and cleaned[1] == ' ')):
            if cleaned[0] == '.' and not (len(cleaned) > 1 and cleaned[1] == ' '):
                break
            cleaned = cleaned[1:].strip()

        cleaned = cleaned.replace('**', '').replace('*', '').replace('__', '').replace('_', '')

        if len(cleaned) < 3:
            continue

        lower_cleaned = cleaned.lower()
        if lower_cleaned in ("summary", "experience", "projects", "skills", "education", "contact info", "contact information"):
            continue

        list_stripped = line_stripped
        while list_stripped and (list_stripped[0] in ('-', '*', '+', '>', ' ', '\t') or list_stripped[0].isdigit() or (list_stripped[0] == '.' and len(list_stripped) > 1 and list_stripped[1] == ' ')):
            if list_stripped[0] == '.' and not (len(list_stripped) > 1 and list_stripped[1] == ' '):
                break
            list_stripped = list_stripped[1:].strip()

        # Allow leniency for job title transitions or role changes
        if '->' in list_stripped or '→' in list_stripped:
            continue
            
        # Allow leniency for lines that are entirely bolded, as these are typically
        # used by the AI for job titles or category headers. Ensure it's reasonably 
        # short to be a header/title (e.g., < 15 words) to avoid skipping full bullet points.
        if list_stripped.startswith('**') and (list_stripped.endswith('**') or list_stripped.endswith('**:')):
            if len(list_stripped.split()) < 15:
                continue

        if step_name == "resume_skills_writeup":
            items = [item.strip() for item in cleaned.split(',')]
            for item in items:
                if not item or len(item) < 2:
                    continue
                if item.endswith(':'):
                    continue
                
                if is_generic_category(item):
                    continue
                    
                normalized_item = normalize_text_alphanumeric(item)
                if normalized_item not in normalized_profile:
                    if ':' in item:
                        parts = item.split(':', 1)
                        skill_part = parts[1].strip()
                        normalized_skill = normalize_text_alphanumeric(skill_part)
                        if normalized_skill and normalized_skill in normalized_profile:
                            continue
                    mismatches.append(item)
        else:
            normalized_line = normalize_text_alphanumeric(cleaned)
            if normalized_line not in normalized_profile:
                mismatches.append(line_stripped)

    return mismatches
