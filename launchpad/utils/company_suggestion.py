"""Company Suggestion — LLM picks companies likely to be a good fit for a resume.

Output is a list of company objects, each with the rationale ("why_fit") tied
to specific evidence from the resume. The user can pass an optional prompt
("remote only", "European Series A", "AI infra") to bias the picks.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a senior career strategist who knows the labour market well. "
    "Given a resume you suggest specific real companies that would be a strong "
    "match for the person, with concrete reasons tied to resume evidence. "
    "Output ONLY valid JSON matching the schema specified in the user's task. "
    "No markdown fences, no preamble. Use null when a field is unknown."
)

# Schema: 10-15 companies. Each entry's "why_fit" must cite resume evidence.
_TASK_TEMPLATE = """\
TASK: Suggest 10-15 real companies likely to hire someone with the resume above.

Rules:
- Real, named companies — not generic categories. Mix established players AND
  smaller / newer ones the user might not have heard of.
- Order by match strength descending.
- Each "why_fit" MUST reference specific resume evidence (a role, a skill, a
  project, a domain) — not generic praise. One concise sentence.
- "match_score" 1-10 — calibrate; reserve 9+ for genuinely strong matches.
- "hiring_likelihood": "high" if the company is actively hiring this profile in
  the broader market; "medium" if they hire occasionally; "low" if it would be
  competitive/aspirational.
- "size": "startup" (<50) | "small" (50-250) | "mid" (250-1000) |
          "large" (1000-10000) | "enterprise" (>10000) | null if unsure.
- "remote_policy": "remote" | "hybrid" | "onsite" | "varies" | null.
- Skip companies the resume already lists as past employers.
{user_prompt_block}
Output JSON (no wrapper, exact schema):
{{
  "companies": [
    {{
      "name":              string,
      "industry":          string | null,
      "size":              "startup"|"small"|"mid"|"large"|"enterprise"|null,
      "location":          string | null,
      "remote_policy":     "remote"|"hybrid"|"onsite"|"varies"|null,
      "website":           string | null,
      "description":       string,
      "why_fit":           string,
      "focus_areas":       [string],
      "hiring_likelihood": "high"|"medium"|"low",
      "match_score":       number
    }}
  ]
}}"""


def _build_task(user_prompt: Optional[str]) -> str:
    block = ""
    if user_prompt and user_prompt.strip():
        block = (
            "\nUser preferences (weight these heavily — skip companies that don't fit):\n"
            + user_prompt.strip()
            + "\n"
        )
    return _TASK_TEMPLATE.format(user_prompt_block=block)


def suggest_companies(
    resume_text: str,
    user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the LLM and return {companies: [...], raw: ...}.

    Raises Exception when all providers fail; caller decides whether to 502
    or return an empty list.
    """
    raw = call_llm_json(
        cached_context=resume_text,
        task=_build_task(user_prompt),
        system=SYSTEM,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("company_suggestion: invalid JSON from LLM: %s", exc)
        return {"companies": [], "raw": None}

    companies = parsed.get("companies") if isinstance(parsed, dict) else None
    if not isinstance(companies, list):
        return {"companies": [], "raw": parsed}

    normalized: List[Dict[str, Any]] = []
    for c in companies:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        normalized.append({
            "name":              str(c.get("name", "")).strip(),
            "industry":          c.get("industry"),
            "size":              _normalize_size(c.get("size")),
            "location":          c.get("location"),
            "remote_policy":     _normalize_remote(c.get("remote_policy")),
            "website":           c.get("website"),
            "description":       str(c.get("description") or "").strip(),
            "why_fit":           str(c.get("why_fit") or "").strip(),
            "focus_areas":       _ensure_str_list(c.get("focus_areas")),
            "hiring_likelihood": _normalize_likelihood(c.get("hiring_likelihood")),
            "match_score":       _normalize_score(c.get("match_score")),
        })

    # Sort by match_score desc as a fallback; the LLM should already order this
    # way but defensive sort handles regressions.
    normalized.sort(key=lambda c: c.get("match_score") or 0, reverse=True)

    return {"companies": normalized, "raw": parsed}


# ── normalization helpers ─────────────────────────────────────────────────────

def _normalize_size(v: Any) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip().lower()
    return s if s in ("startup", "small", "mid", "large", "enterprise") else None


def _normalize_remote(v: Any) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip().lower()
    return s if s in ("remote", "hybrid", "onsite", "varies") else None


def _normalize_likelihood(v: Any) -> str:
    if not v:
        return "medium"
    s = str(v).strip().lower()
    return s if s in ("high", "medium", "low") else "medium"


def _normalize_score(v: Any) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 5.0
    return max(1.0, min(10.0, n))


def _ensure_str_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if x]
