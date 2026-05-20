"""Extract structured data from job description."""

import json
from typing import Dict, Any

try:
    from launchpad.utils.openai_helper import call_ollama_json
except ImportError:
    from utils.openai_helper import call_ollama_json


def extract_jd(jd_text: str, url: str = None) -> Dict[str, Any]:
    """Extract structured data from job description."""
    
    prompt = f"""System:
Extract structured data from this job description.
Output ONLY valid JSON, no markdown fences, no preamble.

Schema:
{{
  "title": string,
  "company": string,
  "seniority": string,
  "reports_to": string | null,
  "team_size": string | null,
  "key_requirements": string[],
  "nice_to_have": string[],
  "domain": string,
  "company_stage": string,
  "location_policy": string,
  "full_text": string
}}

Source: {jd_text}"""

    try:
        result = call_ollama_json(prompt)
        jd_json = json.loads(result)
        if url:
            jd_json["url"] = url
        return jd_json
    except Exception:
        return _fallback_jd_extract(jd_text, url)


def _fallback_jd_extract(jd_text: str, url: str = None) -> Dict[str, Any]:
    """Fallback JD extraction using heuristics."""
    lines = jd_text.split("\n")
    title = lines[0] if lines else "Unknown Role"
    company = "Unknown Company"
    
    for line in lines:
        if "company" in line.lower() or any(c.isupper() for c in line):
            company = line.strip()
            break
    
    return {
        "title": title,
        "company": company,
        "seniority": "unknown",
        "reports_to": None,
        "team_size": None,
        "key_requirements": [r.strip() for r in lines[1:5] if r.strip()],
        "nice_to_have": [],
        "domain": "unknown",
        "company_stage": "unknown",
        "location_policy": "unknown",
        "full_text": jd_text,
        "url": url
    }
