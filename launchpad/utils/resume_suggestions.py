"""Generate resume change suggestions.

Cache strategy
--------------
Reuses the same build_context_block() as scorecard.py so the resume + JD prefix
hits the cache seeded by the prior scorecard call — call 2 in the pipeline pays
only for the task tokens, not the full context again.

Gap trimming
------------
Only gap details + criticality are forwarded in the volatile task slot.
Sending full gap objects (with all their fields) adds unnecessary tokens to
every suggestions call.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

try:
    from launchpad.utils.scorecard import SCORING_SYSTEM, build_context_block
except ImportError:
    from utils.scorecard import SCORING_SYSTEM, build_context_block

_EMPTY_RESULT: Dict[str, Any] = {
    "paraphrasing": [],
    "missing": [],
    "remove": [],
    "polish": [],
}

# ── Task template (volatile) ──────────────────────────────────────────────────
# {gaps}, {override_note}, {user_note} are substituted at call time.
# Everything else is static so the template is allocated once.

_TASK_TEMPLATE = """\
TASK: Generate up to 10 specific, line-level resume edits to improve match against the JD.

Write in second person ("you"/"your"). Never "the candidate".
Every suggestion targets exactly one section: Summary | Job Experience | Education | Skills | Projects | Hobbies.
Do not invent achievements — only reframe what exists, or suggest adding things the user actually has.
Order by impact descending.{override_note}{user_note}

Gaps to address: {gaps}

Output JSON (omit empty arrays):
{{"paraphrasing":[{{"section":str,"original":str,"improved":str,"reason":str,"impact":"high"|"medium"|"low"}}],\
"missing":[{{"section":str,"what_to_add":str,"why_it_matters":str,"jd_reference":str}}],\
"remove":[{{"section":str,"text":str,"reason":str}}],\
"polish":[{{"section":str,"original":str,"improved":str,"reason":str}}]}}"""


def _trim_gaps(gaps: List[Any]) -> List[Dict[str, str]]:
    """Keep only the fields the LLM needs for suggestion generation.

    Full gap objects can include arbitrary metadata.  We only need the details
    and criticality — sending the rest wastes tokens in the volatile task slot.
    """
    trimmed = []
    for g in gaps:
        if isinstance(g, dict):
            trimmed.append({
                "details": str(g.get("details") or g.get("description") or ""),
                "criticality": str(g.get("criticality") or "Medium"),
            })
        else:
            trimmed.append({"details": str(g), "criticality": "Medium"})
    return trimmed


def generate_resume_suggestions(
    resume_text: str,
    jd_json: Dict[str, Any],
    gaps: List[Any],
    override: bool = False,
    user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate specific, line-level resume change suggestions.

    Returns a dict with four buckets — paraphrasing, missing, remove, polish.
    """
    # Reuse the same cached prefix as scorecard (goals=[] keeps the format
    # identical to scorecard's block when goal weights aren't needed here).
    cached_context = build_context_block(resume_text, jd_json, goals=[])

    override_note = (
        "\nNOTE: User is applying despite a skip verdict — lead with best-case framing."
        if override else ""
    )
    user_note = (
        f"\nUser guidance: {user_prompt.strip()}"
        if user_prompt and user_prompt.strip() else ""
    )

    task = _TASK_TEMPLATE.format(
        gaps=json.dumps(_trim_gaps(gaps), separators=(",", ":")),
        override_note=override_note,
        user_note=user_note,
    )

    try:
        raw = call_llm_json(cached_context, task, system=SCORING_SYSTEM)
        parsed = json.loads(raw)
        for key in ("paraphrasing", "missing", "remove", "polish"):
            parsed.setdefault(key, [])
        return parsed
    except Exception as exc:
        logger.warning("generate_resume_suggestions failed: %s", exc)
        return dict(_EMPTY_RESULT)