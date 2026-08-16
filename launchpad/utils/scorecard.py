"""Scorecard analysis + suggestions — single combined LLM call.

Minimisation strategy
---------------------
Previously: 2 separate LLM calls (scorecard → suggestions).
Now:        1 combined call returns both scorecard AND suggestions together.

This saves:
  - 1 full API round-trip (~2-5 seconds wall time)
  - All output tokens for the suggestions call
  - The cache write cost on call 2 (already cached from call 1)

The combined task is slightly longer than the scorecard-only task, but
total tokens = (context once) + (task once) + (output once), vs
old total    = (context twice) + (task twice) + (output twice).

Cache strategy
--------------
cached_context = resume (stripped) + trimmed JD + goals  (stable)
task           = combined scoring + suggestions schema    (volatile)

build_context_block() is exported for verify_loop.py which still runs as a
separate call (only triggered on explicit user action, not automatically).

JD trimming
-----------
full_text and other large prose fields are stripped before serialising the JD.
Saves 300-800 tokens per call.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

from launchpad.utils.models import Scorecard, ScoreDetail

# ── System prompt — byte-identical across all calls ───────────────────────────

SCORING_SYSTEM = (
    "You are a brutally honest career advisor. "
    "You will receive a resume, a job description, and the user's career goals "
    "as a stable context block, followed by a specific task. "
    "Write directly to the user in second person ('you'/'your') — never 'the candidate'. "
    "Output ONLY valid JSON matching the schema in the task. No markdown, no preamble."
)

_JD_STRIP_FIELDS = {"full_text", "raw_text", "description", "body", "html"}


def _trim_jd(jd_json: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in jd_json.items() if k not in _JD_STRIP_FIELDS}


def build_context_block(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
) -> str:
    """Stable cached-context block. Used by scorecard and verify_loop."""
    trimmed_jd = _trim_jd(jd_json)
    return (
        "=== RESUME ===\n"
        f"{resume_text.strip()}\n\n"
        "=== JOB DESCRIPTION ===\n"
        f"{json.dumps(trimmed_jd, separators=(',',':'), sort_keys=True)}\n\n"
        "=== ACTIVE GOALS ===\n"
        f"{json.dumps(goals, separators=(',',':'), sort_keys=True)}"
    )


# ── Combined task (volatile) ──────────────────────────────────────────────────

# _COMBINED_TASK = """\
# TASK: In ONE response, produce both a scorecard AND resume suggestions.

# === PART 1: SCORECARD ===
# Score the resume on each dimension in ACTIVE GOALS.
# - One score per goal (use goal "id"/"label" exactly). Score 1-10. Most scores: 5-8.
# - Anti-inflation: keyword-only mention with no project/role → cap 6.
# - Remark: 1 sentence citing SPECIFIC resume line AND specific JD requirement.
# - overall_fit: weighted mean (high-confidence ×1.5, low ×0.7). 1dp.
# - verdict: "apply" (fit≥7.5, no High gap) | "borderline" (fit 5.5-7.4 or 1 High gap) | "skip" (<5.5 or ≥2 High gaps)
# - summary: 5-7 sentences: overall fit+reason, strongest proof with exact evidence, worst gap+why, 1 interview risk. No filler.
# - gaps: REAL gaps only. type: Skills Gap|Experience Gap|Education Gap|Domain Gap|Seniority Gap|Certification Gap|Soft Skill Gap|Tooling Gap. criticality: High|Medium|Low.

# === PART 2: SUGGESTIONS ===
# Up to 10 line-level resume edits to improve match. Second person. No invented achievements.
# Each targets one section: Summary|Job Experience|Education|Skills|Projects|Hobbies.
# Order by impact descending.

# Output ONE JSON object:
# {"scorecard":{"scores":[{"goal_id":str,"dimension":str,"score":number,"remark":str}],\
# "overall_fit":number,"verdict":"apply"|"borderline"|"skip","summary":str,\
# "gaps":[{"type":str,"details":str,"criticality":"High"|"Medium"|"Low"}]},\
# "suggestions":{"paraphrasing":[{"section":str,"original":str,"improved":str,"reason":str,"impact":"high"|"medium"|"low"}],\
# "missing":[{"section":str,"what_to_add":str,"why_it_matters":str,"jd_reference":str}],\
# "remove":[{"section":str,"text":str,"reason":str}],\
# "polish":[{"section":str,"original":str,"improved":str,"reason":str}]}}"""

_COMBINED_TASK = """\
TASK: In ONE response, produce a scorecard, resume suggestions, and outreach-ready summaries.

=== PART 1: SCORECARD ===
Each ACTIVE GOAL is a job-evaluation metric with a description explaining what it measures and how to score it 1-10. Score the JOB DESCRIPTION against each metric, using the resume and the user's preferences to define the target.
- One score per goal (use goal "id"/"label" exactly). Score 1-10 per the metric's own description.
- The metric description tells you what 1-10 means for that axis — follow it exactly.
- Remark: 1 sentence stating why THIS JOB earned that score on THIS metric, citing the specific JD detail (seniority, company, domain, comp, location) and the candidate's target where relevant.
- overall_fit: weighted mean (high-confidence ×1.5, low ×0.7). 1dp.
- verdict: "apply" (fit>=7.5, no High gap) | "borderline" (fit 5.5-7.4 or 1 High gap) | "skip" (<5.5 or >=2 High gaps)
- summary: 5-7 sentences: overall fit + main reason, best-matching metric, worst-matching metric + why, one thing to weigh before applying. No filler.
- gaps: where the JOB falls short of the candidate's targets. type: Seniority Gap|Domain Gap|Company Fit Gap|Compensation Gap|Location Gap|Skills Gap|Growth Gap. criticality: High|Medium|Low.

=== PART 2: SUGGESTIONS ===
Up to 10 line-level resume edits to strengthen the application for THIS role. Second person. No invented achievements.
Each targets one section: Summary|Job Experience|Education|Skills|Projects|Hobbies.
Order by impact descending.

=== PART 3: OUTREACH MATERIAL ===
job_summary: 3-5 plain factual bullet points (as array of short strings, no "*" or "-") summarizing what THIS role is and what it needs. Draw from JD requirements, seniority, domain, location, compensation if mentioned.
my_relevance: 3-5 plain bullet points (as array of short strings, no "*" or "-") stating why the candidate fits THIS role. MUST cite concrete resume evidence mapped to specific JD requirements. This is outreach pitch material targeting THIS job, not a rewording of metric scores.

Output ONE JSON object:
{"scorecard":{"scores":[{"goal_id":str,"dimension":str,"score":number,"remark":str}],\
"overall_fit":number,"verdict":"apply"|"borderline"|"skip","summary":str,\
"gaps":[{"type":str,"details":str,"criticality":"High"|"Medium"|"Low"}]},\
"suggestions":{"paraphrasing":[{"section":str,"original":str,"improved":str,"reason":str,"impact":"high"|"medium"|"low"}],\
"missing":[{"section":str,"what_to_add":str,"why_it_matters":str,"jd_reference":str}],\
"remove":[{"section":str,"text":str,"reason":str}],\
"polish":[{"section":str,"original":str,"improved":str,"reason":str}]},\
"job_summary":["bullet1","bullet2",...],\
"my_relevance":["bullet1","bullet2",...]}"""


def _make_combined_task(
    gaps_hint: Optional[List[Any]] = None,
    override: bool = False,
    user_prompt: Optional[str] = None,
) -> str:
    """Build the combined task with optional override/user guidance appended."""
    task = _COMBINED_TASK
    if override:
        task += "\nNOTE: User applies despite skip verdict — lead suggestions with best-case framing."
    if user_prompt and user_prompt.strip():
        task += f"\nUser guidance for suggestions: {user_prompt.strip()}"
    return task


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_scorecard_and_suggestions(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
    override: bool = False,
    user_prompt: Optional[str] = None,
) -> tuple[Scorecard, Dict[str, Any], List[str], List[str]]:
    """Single LLM call returning (scorecard, suggestions, job_summary, my_relevance).

    This replaces the old analyze_scorecard() + generate_resume_suggestions()
    two-call pattern.  Returns the same types both functions returned so the
    rest of the pipeline is unchanged, plus two new outreach-ready fields.
    
    Returns:
        tuple: (scorecard, suggestions_dict, job_summary_bullets, my_relevance_bullets)
    """
    cached_context = build_context_block(resume_text, jd_json, goals)
    task = _make_combined_task(override=override, user_prompt=user_prompt)

    try:
        raw = call_llm_json(cached_context, task, system=SCORING_SYSTEM)
        result = json.loads(raw)
        sc_data = result.get("scorecard", {})
        sugg_data = result.get("suggestions", {})
        job_summary = result.get("job_summary", [])
        my_relevance = result.get("my_relevance", [])

        scores = [
            ScoreDetail(
                goal_id=s["goal_id"],
                dimension=s["dimension"],
                score=float(s["score"]),
                remark=s["remark"],
            )
            for s in sc_data.get("scores", [])
        ]
        gaps = [_normalize_gap(g) for g in (sc_data.get("gaps") or [])]

        scorecard = Scorecard(
            scores=scores,
            overall_fit=float(sc_data.get("overall_fit", 5.0)),
            verdict=sc_data.get("verdict", "borderline"),
            summary=sc_data.get("summary", ""),
            gaps=gaps,
        )

        for key in ("paraphrasing", "missing", "remove", "polish"):
            sugg_data.setdefault(key, [])

        # Ensure job_summary and my_relevance are lists of strings
        if not isinstance(job_summary, list):
            job_summary = []
        if not isinstance(my_relevance, list):
            my_relevance = []
        
        # Filter out non-string items and strip whitespace
        job_summary = [str(s).strip() for s in job_summary if s]
        my_relevance = [str(s).strip() for s in my_relevance if s]

        return scorecard, sugg_data, job_summary, my_relevance

    except Exception as exc:
        logger.warning("analyze_scorecard_and_suggestions failed: %s", exc)
        return _fallback_scorecard(goals), {"paraphrasing": [], "missing": [], "remove": [], "polish": []}, [], []


# Keep the old single-output function as a thin wrapper for verify_loop compat
def analyze_scorecard(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]],
) -> Scorecard:
    """Scorecard-only call (used by verify_loop). Prefer analyze_scorecard_and_suggestions."""
    sc, _, _, _ = analyze_scorecard_and_suggestions(resume_text, jd_json, goals)
    return sc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_gap(gap: Any) -> Dict[str, str]:
    if isinstance(gap, dict):
        return {
            "type": str(gap.get("type") or "Skills Gap"),
            "details": str(gap.get("details") or gap.get("description") or ""),
            "criticality": _normalize_criticality(gap.get("criticality")),
        }
    text = str(gap)
    low = text.lower()
    criticality = (
        "High" if any(w in low for w in ("required", "must", "essential", "critical"))
        else "Low" if any(w in low for w in ("nice", "preferred", "bonus", "plus"))
        else "Medium"
    )
    return {"type": "Skills Gap", "details": text, "criticality": criticality}


def _normalize_criticality(value: Any) -> str:
    if not value:
        return "Medium"
    v = str(value).strip().capitalize()
    return v if v in ("High", "Medium", "Low") else "Medium"


def _fallback_scorecard(goals: List[Dict[str, Any]]) -> Scorecard:
    return Scorecard(
        scores=[
            ScoreDetail(
                goal_id=g.get("id", "unknown"),
                dimension=g.get("label", "Unknown"),
                score=5.0,
                remark="Unable to analyze — all LLM providers unavailable.",
            )
            for g in goals
        ],
        overall_fit=5.0,
        verdict="borderline",
        summary="Analysis unavailable. Check your API keys or Ollama connection and try again.",
        gaps=[],
    )