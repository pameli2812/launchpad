"""Verify loop - Compare original vs updated resume."""

import json
from datetime import datetime
from typing import Any, Dict, List

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

try:
    from launchpad.utils.scorecard import SCORING_SYSTEM, build_context_block
except ImportError:
    from utils.scorecard import SCORING_SYSTEM, build_context_block

from launchpad.utils.models import VerifyAttempt


def verify_and_rescore(
    resume_original: str,
    resume_updated: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
    attempt_number: int = 1,
) -> VerifyAttempt:
    """Compare original vs updated resume and rescore.

    Cached prefix is the same `resume_original + JD + goals` block used by
    scorecard/suggestions, so the third call in an analysis pipeline hits the cache.
    The updated resume is part of the volatile task slot (it differs per attempt).
    """

    cached_context = build_context_block(resume_original, jd_json, goals)

    verdict_constraint = (
        "must be 'good_to_proceed' or 'apply_with_caveats' — close the loop"
        if attempt_number >= 2
        else "use the verdict that genuinely fits"
    )

    task = f"""TASK: Compare the revised resume against the original (in the context block above) for the same JD and goals.

Rules:
- Score both versions against the JD and goals independently.
- Identify which specific gaps were closed and which remain.
- attempt_number {attempt_number}: verdict {verdict_constraint}.
- Be direct — no encouragement.

Output JSON schema:
{{
  "score_before": number,
  "score_after": number,
  "delta": number,
  "gaps_closed": [str],
  "gaps_remaining": [str],
  "verdict": "good_to_proceed"|"apply_with_caveats"|"needs_more_work",
  "verdict_message": str,
  "attempt_number": number
}}

=== RESUME V2 (UPDATED) ===
{resume_updated}

Attempt number: {attempt_number}"""

    try:
        result = call_llm_json(cached_context, task, system=SCORING_SYSTEM)
        result_json = json.loads(result)

        return VerifyAttempt(
            attempt_number=attempt_number,
            score_before=float(result_json.get("score_before", 5.0)),
            score_after=float(result_json.get("score_after", 5.0)),
            delta=float(result_json.get("delta", 0.0)),
            gaps_closed=result_json.get("gaps_closed", []),
            gaps_remaining=result_json.get("gaps_remaining", []),
            verdict=result_json.get("verdict", "needs_more_work"),
            verdict_message=result_json.get("verdict_message", ""),
            timestamp=datetime.now(),
        )
    except Exception:
        return VerifyAttempt(
            attempt_number=attempt_number,
            score_before=5.0,
            score_after=5.0,
            delta=0.0,
            gaps_closed=[],
            gaps_remaining=[],
            verdict="needs_more_work",
            verdict_message="Unable to verify — all LLM providers unavailable.",
            timestamp=datetime.now(),
        )
