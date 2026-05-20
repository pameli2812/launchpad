"""Generate resume change suggestions.

Reuses the same cached context block as scorecard.py so the resume + JD + goals
prefix hits the cache from the prior scorecard call.
"""

import json
from typing import Any, Dict, List, Optional

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

try:
    from launchpad.utils.scorecard import SCORING_SYSTEM, build_context_block
except ImportError:
    from utils.scorecard import SCORING_SYSTEM, build_context_block


def generate_resume_suggestions(
    resume_text: str,
    jd_json: Dict[str, Any],
    gaps: List[Any],
    override: bool = False,
    user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate specific, line-level resume change suggestions.

    Returns a dict with four buckets — paraphrasing (Text Edit), missing
    (Add Data), remove (Remove Text), polish (Polish Content). Each item
    targets one of: Summary, Job Experience, Education, Skills, Projects,
    Hobbies.
    """

    # Same cached prefix as scorecard. Goals aren't strictly needed for
    # suggestions, but reusing the block means the cache hits on call 2.
    cached_context = build_context_block(resume_text, jd_json, goals=[])

    gaps_str = json.dumps(gaps, default=str)

    override_context = ""
    if override:
        override_context = (
            "\nNOTE: You are choosing to apply despite a skip verdict. "
            "Lead with best-case framing — what your resume can realistically achieve."
        )

    user_guidance = ""
    if user_prompt and user_prompt.strip():
        user_guidance = (
            "\n\nUser guidance (take this into account when choosing what to suggest):\n"
            + user_prompt.strip()
        )

    task = f"""TASK: Generate specific, line-level resume change suggestions to improve this resume's match against the JD.

Write directly to the user using second person ("you", "your"). Never use "the candidate".

Rules:
- Every suggestion must target exactly one of these sections:
  Summary, Job Experience, Education, Skills, Projects, Hobbies.
- Paraphrasing (Text Edit): EXACT original text from the resume -> improved text.
  Must be copy-pasteable.
- Polish (Polish Content): tighten wording, fix passive voice, add metrics — original
  must exist in the resume.
- Missing (Add Data): describe what to add, which section, and why it matters for
  this JD (quote JD language). For missing items, "before" should be "No change".
- Remove (Remove Text): content that hurts this application (off-topic experience,
  dated tech).
- Do not invent achievements. Only suggest reframing what already exists, or adding
  things the user actually has.
- Max 10 total changes across all four buckets, ordered by impact descending.

Output JSON schema:
{{
  "paraphrasing": [{{
    "section": "Summary"|"Job Experience"|"Education"|"Skills"|"Projects"|"Hobbies",
    "original": str, "improved": str, "reason": str,
    "impact": "high"|"medium"|"low"
  }}],
  "missing": [{{
    "section": str, "what_to_add": str, "why_it_matters": str, "jd_reference": str
  }}],
  "remove": [{{"section": str, "text": str, "reason": str}}],
  "polish": [{{"section": str, "original": str, "improved": str, "reason": str}}]
}}
{override_context}{user_guidance}

Identified gaps to address: {gaps_str}"""

    try:
        result = call_llm_json(cached_context, task, system=SCORING_SYSTEM)
        parsed = json.loads(result)
        for key in ("paraphrasing", "missing", "remove", "polish"):
            parsed.setdefault(key, [])
        return parsed
    except Exception:
        return {
            "paraphrasing": [],
            "missing": [],
            "remove": [],
            "polish": [],
        }
