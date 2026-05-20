"""Verify loop - Compare original vs updated resume."""

import json
from typing import Dict, Any, List
from analyser.launchpad.utils.openai_helper import call_ollama_json
from analyser.launchpad.utils.models import VerifyAttempt
from datetime import datetime


def verify_and_rescore(
    resume_original: str,
    resume_updated: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
    attempt_number: int = 1
) -> VerifyAttempt:
    """Compare original vs updated resume and rescore."""
    
    goals_str = json.dumps(goals, indent=2)
    jd_str = json.dumps(jd_json, indent=2)
    
    verdict_constraint = "must be 'good_to_proceed' or 'apply_with_caveats' — close the loop" if attempt_number == 2 else ""
    
    prompt = f"""System:
Compare a revised resume against the original for this JD and goals.
Output a score delta and a verdict. Be direct — no encouragement.

Rules:
- Score both versions against the same JD and goals independently.
- Identify which specific gaps were closed and which remain.
- If attempt_number is 2, close the loop: verdict {verdict_constraint}
- Output ONLY valid JSON. No markdown.

Schema:
{{
  "score_before": number,
  "score_after": number,
  "delta": number,
  "gaps_closed": string[],
  "gaps_remaining": string[],
  "verdict": "good_to_proceed"|"apply_with_caveats"|"needs_more_work",
  "verdict_message": string,
  "attempt_number": number
}}

Goals: {goals_str}

JD: {jd_str}

Resume v1 (original): {resume_original}

Resume v2 (updated): {resume_updated}

Attempt number: {attempt_number}"""

    try:
        result = call_ollama_json(prompt)
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
            timestamp=datetime.now()
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
            verdict_message="Unable to verify due to API issues",
            timestamp=datetime.now()
        )
