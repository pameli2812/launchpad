"""Scorecard analysis - Score resume against JD.

Cache strategy: the resume + JD + goals are emitted as a stable user-message
block with cache_control. Same block is used by resume_suggestions and
verify_loop so all three calls in one analysis share a cached prefix.
"""

import json
from typing import Any, Dict, List

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

from launchpad.utils.models import Scorecard, ScoreDetail


# Generic system prompt — kept stable across scorecard / suggestions / verify
# so the cached user-message prefix actually hits.
SCORING_SYSTEM = (
    "You are a brutally honest career advisor. You will receive a resume, a job "
    "description, and the user's locked career goals as a stable context block, "
    "followed by a specific task. Always write directly to the user in second "
    "person ('you', 'your') — never 'the candidate'. Output ONLY valid JSON "
    "matching the schema in the task. No markdown, no preamble."
)


def build_context_block(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
) -> str:
    """Build the cached context block. Same format across scorecard / suggestions
    / verify so the prefix is byte-identical and the cache hits."""
    return (
        "=== RESUME ===\n"
        f"{resume_text}\n\n"
        "=== JOB DESCRIPTION ===\n"
        f"{json.dumps(jd_json, indent=2, sort_keys=True)}\n\n"
        "=== ACTIVE GOALS ===\n"
        f"{json.dumps(goals, indent=2, sort_keys=True)}"
    )


def analyze_scorecard(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
) -> Scorecard:
    """Score resume against JD using locked goals."""

    cached_context = build_context_block(resume_text, jd_json, goals)

    task = """TASK: Score the resume against the JD using the goals as scoring dimensions.

Rules:
- One score per goal dimension. Score 1–10. No inflation.
- Remarks must cite specific resume content or JD language — not generic.
- overall_fit = weighted mean. Weight higher the dimensions marked high-confidence.
- verdict: "apply" (>=7.5), "borderline" (5.5-7.4), "skip" (<5.5).
- summary: 5-7 descriptive sentences in second person. Must stand on its own:
    * overall fit and why,
    * single biggest strength with concrete evidence,
    * single biggest real gap and what makes it hurt,
    * one interview risk you should know about.
- gaps: STRUCTURED objects with:
    * type: one of "Skills Gap", "Experience Gap", "Education Gap", "Domain Gap",
            "Seniority Gap", "Certification Gap", "Soft Skill Gap", "Tooling Gap".
    * details: one specific, fixable-by-resume-edit gap, written in second person.
    * criticality: "High" (JD required/must-have), "Medium" (preferred or repeated),
                   "Low" (nice-to-have).
  Only include gaps that are real AND addressable by resume edits.

Output JSON schema:
{
  "scores": [{"goal_id": str, "dimension": str, "score": number, "remark": str}],
  "overall_fit": number,
  "verdict": "apply" | "borderline" | "skip",
  "summary": str,
  "gaps": [{"type": str, "details": str, "criticality": "High"|"Medium"|"Low"}]
}"""

    try:
        result = call_llm_json(cached_context, task, system=SCORING_SYSTEM)
        result_json = json.loads(result)

        scores = [
            ScoreDetail(
                goal_id=s["goal_id"],
                dimension=s["dimension"],
                score=float(s["score"]),
                remark=s["remark"],
            )
            for s in result_json.get("scores", [])
        ]

        raw_gaps = result_json.get("gaps", []) or []
        gaps = [_normalize_gap(g) for g in raw_gaps]

        return Scorecard(
            scores=scores,
            overall_fit=float(result_json.get("overall_fit", 5.0)),
            verdict=result_json.get("verdict", "borderline"),
            summary=result_json.get("summary", ""),
            gaps=gaps,
        )
    except Exception:
        return _fallback_scorecard(goals)


def _normalize_gap(gap: Any) -> Dict[str, str]:
    """Coerce a gap (string OR dict) into the structured shape the UI expects."""
    if isinstance(gap, dict):
        return {
            "type": str(gap.get("type") or "Skills Gap"),
            "details": str(gap.get("details") or gap.get("description") or ""),
            "criticality": _normalize_criticality(gap.get("criticality")),
        }
    text = str(gap)
    lowered = text.lower()
    if any(w in lowered for w in ("required", "must", "essential", "critical")):
        criticality = "High"
    elif any(w in lowered for w in ("nice", "preferred", "bonus", "plus")):
        criticality = "Low"
    else:
        criticality = "Medium"
    return {"type": "Skills Gap", "details": text, "criticality": criticality}


def _normalize_criticality(value: Any) -> str:
    if not value:
        return "Medium"
    v = str(value).strip().capitalize()
    return v if v in ("High", "Medium", "Low") else "Medium"


def _fallback_scorecard(goals: List[Dict[str, Any]]) -> Scorecard:
    scores = [
        ScoreDetail(
            goal_id=g.get("id", "unknown"),
            dimension=g.get("label", "Unknown"),
            score=5.0,
            remark="Unable to analyze — all LLM providers unavailable.",
        )
        for g in goals
    ]
    return Scorecard(
        scores=scores,
        overall_fit=5.0,
        verdict="borderline",
        summary="Analysis unavailable. Check your API keys or Ollama connection and try again.",
        gaps=[],
    )
