"""
Analysis routes - Handle resume analysis and scoring
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import sys
from pathlib import Path

# Import from launchpad utils
from utils.matcher import analyze_resume_vs_goal
from utils.scorecard import calculate_match_score
from utils.resume_suggestions import generate_suggestions
from utils.models import AnalysisRequest

router = APIRouter()

# ─────────────────────────────────────────────
# Analysis Endpoints
# ─────────────────────────────────────────────

@router.post("/run")
async def run_analysis(
    resume_id: str,
    goal_set_id: str,
    job_description: str,
):
    """
    Run analysis on a resume against job description and goal set
    """
    try:
        # Call your existing analysis logic
        result = analyze_resume_vs_goal(
            resume_id=resume_id,
            goal_set_id=goal_set_id,
            job_description=job_description,
        )
        
        return {
            "analysis": result,
            "status": "success",
            "message": "Analysis completed",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score")
async def calculate_score(
    resume_text: str,
    job_description: str,
    goal_description: Optional[str] = None,
):
    """
    Calculate match score between resume and JD
    """
    try:
        score = calculate_match_score(resume_text, job_description, goal_description)
        return {
            "score": score,
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions")
async def get_suggestions(
    resume_text: str,
    job_description: str,
    analysis_gaps: Optional[dict] = None,
):
    """
    Generate improvement suggestions based on analysis
    """
    try:
        suggestions = generate_suggestions(
            resume_text=resume_text,
            job_description=job_description,
            gaps=analysis_gaps,
        )
        
        return {
            "suggestions": suggestions,
            "status": "success",
            "message": "Suggestions generated",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
