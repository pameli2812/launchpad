"""Extract structured data from a job description.

Minimisation strategy
---------------------
Heuristic pass runs first — free, instant, no API cost.
LLM is called ONLY when heuristics produce low-confidence results
(title/company still unknown, or fewer than 3 requirements found).

In practice:
  - Clean structured JDs (LinkedIn, Greenhouse, Lever): heuristics win → 0 LLM calls
  - Free-form pasted text: heuristics extract what they can, LLM fills the gaps

full_text is intentionally excluded from the returned dict — scorecard.py
strips it anyway and it wastes tokens in every downstream cached context block.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

# ── LLM task ──────────────────────────────────────────────────────────────────

_EXTRACT_TASK = (
    'TASK: Extract structured fields from this job description. '
    'Output ONLY compact JSON: '
    '{"title":str,"company":str,"seniority":str,"reports_to":str|null,'
    '"team_size":str|null,"key_requirements":str[],"nice_to_have":str[],'
    '"domain":str,"company_stage":str,"location_policy":str,'
    '"verified_email":str|null,"recipient_type":str|null,"contact_name":str|null} '
    'No full_text field. No markdown. No preamble.'
)

_EXTRACT_SYSTEM = (
    "You are a precise data extractor. "
    "Output ONLY valid JSON. No markdown fences, no preamble, no trailing prose."
)

# ── Heuristic tables ──────────────────────────────────────────────────────────

_SENIORITY_PATTERNS = [
    (r"\b(cto|cpo|ceo|chief\b)", "c-suite"),
    (r"\b(vp|vice president)\b", "vp"),
    (r"\b(director|head of)\b", "director"),
    (r"\b(principal|staff)\b", "principal"),
    (r"\b(senior|sr\.?)\b", "senior"),
    (r"\b(lead)\b", "lead"),
    (r"\b(mid.?level)\b", "mid"),
    (r"\b(junior|jr\.?|associate|entry.?level)\b", "junior"),
    (r"\b(intern)\b", "intern"),
]

_REMOTE_PATTERNS = [
    (r"\b(fully remote|remote.first|100%\s*remote)\b", "remote"),
    (r"\b(hybrid)\b", "hybrid"),
    (r"\b(on.?site|in.office|in.person)\b", "on-site"),
]


def _extract_bullets(lines: List[str], start_idx: int, max_items: int = 10) -> List[str]:
    items: List[str] = []
    for line in lines[start_idx:]:
        if re.match(r"^[-•*\d]", line):
            clean = re.sub(r"^[-•*]\s*|\d+\.\s*", "", line).strip()
            if 10 < len(clean) < 200:
                items.append(clean)
        elif items:
            break  # non-bullet after collecting some = new section
        if len(items) >= max_items:
            break
    return items


def _heuristic_extract(jd_text: str, url: Optional[str]) -> Dict[str, Any]:
    lines = [l.strip() for l in jd_text.split("\n") if l.strip()]
    text_lower = jd_text.lower()

    # Title — first short line (≤8 words, no period) in the first 5 lines
    title = "Unknown Role"
    for line in lines[:5]:
        if len(line.split()) <= 8 and "." not in line:
            title = line
            break

    # Company — common patterns
    company = "Unknown Company"
    for pat in [
        r"(?:at|@)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Company:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"^([A-Z][A-Za-z0-9\s&]{2,30})\s+is\s+(?:hiring|looking|seeking)",
    ]:
        m = re.search(pat, jd_text, re.MULTILINE)
        if m:
            company = m.group(1).strip().rstrip(".,")
            break

    # Seniority
    seniority = "mid"
    combined = (title + " " + jd_text[:500]).lower()
    for pattern, level in _SENIORITY_PATTERNS:
        if re.search(pattern, combined):
            seniority = level
            break

    # Location policy
    location_policy = "unknown"
    for pattern, policy in _REMOTE_PATTERNS:
        if re.search(pattern, text_lower):
            location_policy = policy
            break

    # Requirements and nice-to-haves from bullet sections
    key_requirements: List[str] = []
    nice_to_have: List[str] = []
    req_headers = re.compile(
        r"^(requirements?|qualifications?|what you.ll do|must.have|responsibilities)",
        re.IGNORECASE,
    )
    nth_headers = re.compile(
        r"^(nice.to.have|preferred|bonus|plus|ideally|good to have)",
        re.IGNORECASE,
    )
    for i, line in enumerate(lines):
        if req_headers.match(line) and not key_requirements:
            key_requirements = _extract_bullets(lines, i + 1, max_items=10)
        if nth_headers.match(line) and not nice_to_have:
            nice_to_have = _extract_bullets(lines, i + 1, max_items=5)

    verified_email = None
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", jd_text, re.IGNORECASE)
    if match:
        verified_email = match.group(0).strip()

    recipient_type = None
    lowered = jd_text.lower()
    if "recruiter" in lowered or "talent partner" in lowered:
        recipient_type = "recruiter"
    elif "hiring manager" in lowered or "hiring manager" in lowered:
        recipient_type = "hiring_manager"
    elif "hr" in lowered:
        recipient_type = "hr"

    contact_name = None
    contact_match = re.search(r"(?:contact|hi)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", jd_text)
    if contact_match:
        contact_name = contact_match.group(1).strip()

    result: Dict[str, Any] = {
        "title": title,
        "company": company,
        "seniority": seniority,
        "reports_to": None,
        "team_size": None,
        "key_requirements": key_requirements,
        "nice_to_have": nice_to_have,
        "domain": "unknown",
        "company_stage": "unknown",
        "location_policy": location_policy,
        "verified_email": verified_email,
        "recipient_type": recipient_type,
        "contact_name": contact_name,
    }
    if url:
        result["url"] = url
    return result


def _high_confidence(jd: Dict[str, Any]) -> bool:
    return (
        jd["title"] != "Unknown Role"
        and jd["company"] != "Unknown Company"
        and len(jd["key_requirements"]) >= 3
    )


# ── Public API ────────────────────────────────────────────────────────────────

def extract_jd(jd_text: str, url: Optional[str] = None) -> Dict[str, Any]:
    """Extract structured JD fields — heuristics first, LLM only as fallback."""
    jd = _heuristic_extract(jd_text, url)

    if _high_confidence(jd):
        logger.info(
            "jd_extraction: heuristics OK (title=%r company=%r reqs=%d)",
            jd["title"], jd["company"], len(jd["key_requirements"]),
        )
        return jd

    logger.info("jd_extraction: low confidence — calling LLM")
    try:
        raw = call_llm_json(
            cached_context=jd_text,
            task=_EXTRACT_TASK,
            system=_EXTRACT_SYSTEM,
            timeout=30,
        )
        result = json.loads(raw)
        result.pop("full_text", None)
        result.setdefault("verified_email", None)
        result.setdefault("recipient_type", None)
        result.setdefault("contact_name", None)
        if url:
            result["url"] = url
        return result
    except Exception as exc:
        logger.warning("jd_extraction LLM failed: %s — using heuristic result", exc)
        return jd