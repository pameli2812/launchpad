"""Scorecard analysis - Score resume against JD."""

import json
from typing import List, Dict, Any
from utils.openai_helper import call_ollama_json
from utils.models import Scorecard, ScoreDetail


def analyze_scorecard(
    resume_text: str,
    jd_json: Dict[str, Any],
    goals: List[Dict[str, Any]]
) -> Scorecard:
    """Score resume against JD using locked goals."""
    
    goals_str = json.dumps(goals, indent=2)
    jd_str = json.dumps(jd_json, indent=2)
    
    prompt = f"""System:
You are a brutally honest career advisor. Score this resume against 
this JD using only the user's locked goals as scoring dimensions.

Rules:
- One score per goal dimension. Score 1–10. No inflation.
- Remarks must cite specific resume content or JD language — not generic.
- overall_fit = weighted mean. Weight higher the dimensions marked 
  high-confidence in goals.
- verdict: "apply" (≥7.5), "borderline" (5.5–7.4), "skip" (<5.5)
- summary: 4–6 sentences. Biggest strength, biggest real gap, 
  one interview risk worth knowing.
- gaps: list only gaps that are both present AND fixable by resume edits.
- Output ONLY valid JSON. No markdown.

Schema:
{{
  "scores": [{{
    "goal_id": string,
    "dimension": string,
    "score": number,
    "remark": string
  }}],
  "overall_fit": number,
  "verdict": "apply"|"borderline"|"skip",
  "summary": string,
  "gaps": string[]
}}

Active goals: {goals_str}

Resume: {resume_text}

JD: {jd_str}"""

    try:
        result = call_ollama_json(prompt)
        result_json = json.loads(result)
        
        scores = [
            ScoreDetail(
                goal_id=s["goal_id"],
                dimension=s["dimension"],
                score=float(s["score"]),
                remark=s["remark"]
            )
            for s in result_json.get("scores", [])
        ]
        
        return Scorecard(
            scores=scores,
            overall_fit=float(result_json.get("overall_fit", 5.0)),
            verdict=result_json.get("verdict", "borderline"),
            summary=result_json.get("summary", ""),
            gaps=result_json.get("gaps", [])
        )
    except Exception as e:
        # Fallback scorecard
        return _fallback_scorecard(goals)


def _fallback_scorecard(goals: List[Dict[str, Any]]) -> Scorecard:
    """Fallback scorecard using keyword matching."""
    scores = [
        ScoreDetail(
            goal_id=g.get("id", "unknown"),
            dimension=g.get("label", "Unknown"),
            score=5.0,
            remark="Unable to analyze due to API issues"
        )
        for g in goals
    ]
    
    return Scorecard(
        scores=scores,
        overall_fit=5.0,
        verdict="borderline",
        summary="Analysis unavailable. Please check Ollama connection or try again.",
        gaps=[]
    )
