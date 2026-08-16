"""Resume Review — LLM-driven structured-profile extraction.

Reads a resume's already-extracted text (PDF parsing happens at upload time)
and returns a JSON object with contact info, summary, skills, work history,
education, certifications and projects.

The result is persisted into the resume_reviews table so we only pay the LLM
cost once per resume (keyed by resume_id, not content_hash, so re-uploading
the same resume with edits gives a fresh review).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

logger = logging.getLogger(__name__)

REVIEW_SYSTEM = (
    "You extract structured profile data from resumes. "
    "Output ONLY valid JSON matching the schema specified in the user's task. "
    "No markdown fences, no preamble, no trailing prose. "
    "Use null (not empty string) for fields you cannot find. "
    "Preserve original wording from the resume — do not paraphrase, summarize, "
    "or invent content. If a field genuinely isn't in the resume, leave it null."
)

_TASK = """\
TASK: Extract a structured profile from the resume above.

Rules:
- Use exact wording from the resume. Do NOT paraphrase or invent.
- Use null when a field genuinely isn't present in the resume.
- For dates, prefer the resume's format (e.g. "Jan 2024", "2020-Present").
- Sort experience newest-first by start_date. Same for education.
- The headline is one short line (e.g. "Senior Product Manager · AI/GenAI · 8 yrs")
  derived from the resume — do not write a marketing tagline.
- Skills: include both hard skills (tools, languages) and notable methodologies.
  Skip generic soft skills like "team player" unless the resume calls them out.

Output JSON (no wrapper, exact schema):
{
  "full_name":      string | null,
  "email":          string | null,
  "phone":          string | null,
  "location":       string | null,
  "linkedin":       string | null,
  "headline":       string | null,
  "summary":        string | null,
  "skills":         [{"name": string, "category": string | null}],
  "experience": [
    {
      "title":       string,
      "company":     string,
      "location":    string | null,
      "start_date":  string | null,
      "end_date":    string | null,
      "current":     boolean,
      "description": string | null,
      "achievements": [string]
    }
  ],
  "education": [
    {
      "institution": string,
      "degree":      string | null,
      "field":       string | null,
      "start_date":  string | null,
      "end_date":    string | null,
      "gpa":         string | null
    }
  ],
  "certifications": [
    {"name": string, "issuer": string | null, "date": string | null}
  ],
  "projects": [
    {"name": string, "description": string | null, "tech": [string], "url": string | null}
  ]
}"""

# Top-level keys we always expect — used to normalize partial LLM responses
_EXPECTED_KEYS = {
    "full_name": None, "email": None, "phone": None, "location": None,
    "linkedin": None, "headline": None, "summary": None,
    "skills": [], "experience": [], "education": [],
    "certifications": [], "projects": [],
}


def extract_resume_profile(resume_text: str) -> Dict[str, Any]:
    """Run the LLM extraction and return a normalized dict.

    Raises Exception if all providers in the chain fail (caller decides whether
    to surface as a 502 or silently return an empty profile).
    """
    raw = call_llm_json(
        cached_context=resume_text,
        task=_TASK,
        system=REVIEW_SYSTEM,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("resume_review: LLM returned invalid JSON: %s", exc)
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    # Fill missing keys with empty defaults so the DB write below never KeyErrors
    out: Dict[str, Any] = {}
    for key, default in _EXPECTED_KEYS.items():
        v = parsed.get(key, default)
        # Coerce wrong types back to defaults rather than crashing
        if isinstance(default, list) and not isinstance(v, list):
            v = []
        if not isinstance(default, list) and isinstance(v, list):
            v = None
        out[key] = v

    # Keep the raw response too — it powers future schema migrations without
    # re-paying the LLM cost.
    out["raw"] = parsed
    return out
