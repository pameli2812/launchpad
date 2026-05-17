"""Generate resume change suggestions."""

import json
from typing import Dict, Any, List
from utils.openai_helper import call_ollama_json


def generate_resume_suggestions(
    resume_text: str,
    jd_json: Dict[str, Any],
    gaps: List[str],
    override: bool = False
) -> Dict[str, Any]:
    """Generate specific resume change suggestions."""

    gaps_str = json.dumps(gaps)
    jd_str = json.dumps(jd_json, indent=2)
    override_context = ""

    if override:
        override_context = "NOTE: The user is choosing to apply despite a skip verdict. Lead with best-case framing — what their resume can realistically achieve."

    prompt = f"""System:
Generate specific, line-level resume change suggestions to improve this resume's match against the JD.

CRITICAL LANGUAGE RULE:
- NEVER use "the candidate", "the applicant", "they", or any third-person language.
- ALWAYS write directly to the user using second person: "you", "your", "your resume".
- Example WRONG: "The candidate should add AWS experience to their skills section."
- Example RIGHT: "Add your AWS experience to your Skills section — the JD lists it as a required qualification."
- All fields (what_to_add, why_it_matters, reason, improved) must use second-person language.

Rules:
- Paraphrasing: EXACT original text → EXACT improved text. Must be copy-pasteable. Never generalize.
- Do not invent new achievements. Only reframe what already exists in the resume.
- Missing items: describe exactly what to add, which section, and why it matters for this JD (quote JD language).
- Max 8 total changes. Order by impact descending.
- Output ONLY valid JSON. No markdown.

Schema:
{{
  "override_context": string | null,
  "paraphrasing": [{{
    "section": string,
    "original": string,
    "improved": string,
    "reason": string,
    "impact": "high"|"medium"|"low"
  }}],
  "missing": [{{
    "section": string,
    "what_to_add": string,
    "why_it_matters": string,
    "jd_reference": string
  }}]
}}

{override_context}

Resume: {resume_text}

JD: {jd_str}

Identified gaps: {gaps_str}"""

    try:
        result = call_ollama_json(prompt)
        return json.loads(result)
    except Exception:
        return {
            "override_context": None,
            "paraphrasing": [],
            "missing": []
        }