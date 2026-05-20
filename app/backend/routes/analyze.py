"""
Analysis routes — extract JD, score against goals, and generate suggestions.
"""

import hashlib
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from launchpad.utils.parser import extract_text_from_pdf
from launchpad.utils.pdf_viewer import UPLOAD_DIR
from launchpad.utils.storage import read_json, write_json
from launchpad.utils.jd_extraction import extract_jd
from launchpad.utils.scorecard import analyze_scorecard
from launchpad.utils.resume_suggestions import generate_resume_suggestions
from launchpad.utils.pdf_editor import apply_changes as apply_pdf_changes

router = APIRouter()

# Same anchored path the setup route uses, so React + Streamlit share storage.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOAL_SETS_FILE = str(_PROJECT_ROOT / "launchpad" / "data" / "goal_sets.json")
HISTORY_FILE = str(_PROJECT_ROOT / "launchpad" / "data" / "history.json")


# ─────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────

class RunAnalysisIn(BaseModel):
    resume_name: str
    goal_set_id: str
    jd_text: Optional[str] = None
    jd_url: Optional[str] = None


class SuggestionsIn(BaseModel):
    resume_name: str
    jd_json: Dict[str, Any]
    gaps: List[Any] = []
    user_prompt: Optional[str] = None
    override: bool = False


class AcceptedChange(BaseModel):
    type: str  # "Text Edit" | "Add Data" | "Remove Text" | "Polish Content"
    section: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None


class ApplySuggestionsIn(BaseModel):
    resume_name: str
    accepted_changes: List[AcceptedChange]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _resolve_resume_path(resume_name: str) -> Path:
    candidate = (UPLOAD_DIR / resume_name).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if upload_root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid resume name")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    return candidate


def _read_resume_bytes(resume_name: str) -> bytes:
    with open(_resolve_resume_path(resume_name), "rb") as f:
        return f.read()


def _read_resume_text(resume_name: str) -> str:
    return extract_text_from_pdf(BytesIO(_read_resume_bytes(resume_name)))


def _load_goal_set(goal_set_id: str) -> Dict[str, Any]:
    data = read_json(GOAL_SETS_FILE, default={"goal_sets": []})
    for gs in data.get("goal_sets", []):
        if gs["id"] == goal_set_id:
            return gs
    raise HTTPException(status_code=404, detail=f"Goal set {goal_set_id} not found")


def _resume_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _append_history(entry: Dict[str, Any]) -> None:
    history = read_json(HISTORY_FILE, default=[]) or []
    if not isinstance(history, list):
        history = []
    history.append(entry)
    write_json(HISTORY_FILE, history)


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post("/run")
async def run_analysis(payload: RunAnalysisIn):
    """End-to-end analysis: extract JD → score against goals → auto-save to history."""
    if not (payload.jd_text or payload.jd_url):
        raise HTTPException(status_code=400, detail="Provide jd_text or jd_url")

    resume_text = _read_resume_text(payload.resume_name)
    goal_set = _load_goal_set(payload.goal_set_id)

    goals = [
        {
            "id": g.get("id"),
            "label": g.get("label"),
            "description": g.get("description", ""),
            "confidence": g.get("confidence", "high"),
        }
        for g in goal_set.get("goals", [])
    ]

    try:
        jd_json = extract_jd(payload.jd_text or "", payload.jd_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD extraction failed: {e}")

    try:
        scorecard = analyze_scorecard(resume_text, jd_json, goals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")

    jd_id = str(uuid.uuid4())[:8]
    entry = {
        "jd_id": jd_id,
        "analyzed_at": datetime.now().isoformat(),
        "goal_set_id": goal_set["id"],
        "goal_set_name": goal_set["name"],
        "goal_set_snapshot": goal_set.get("goals", []),
        "resume_id": payload.resume_name,
        "resume_snapshot_hash": _resume_hash(resume_text),
        "scorecard": scorecard.to_dict(),
        "verdict": scorecard.verdict,
        "overall_fit": scorecard.overall_fit,
        "status": "pending",
        "changes_generated": False,
        "jd_title": jd_json.get("title", "?"),
        "company": jd_json.get("company", "?"),
        "url": jd_json.get("url"),
        "suggestions": None,
    }
    try:
        _append_history(entry)
    except Exception:
        # History persistence shouldn't block returning the result.
        pass

    return {
        "jd_id": jd_id,
        "jd": jd_json,
        "scorecard": scorecard.to_dict(),
        "resume_name": payload.resume_name,
        "goal_set_id": goal_set["id"],
        "goal_set_name": goal_set["name"],
    }


@router.post("/suggestions")
async def get_suggestions(payload: SuggestionsIn):
    """Generate (or regenerate) suggestions for the most recent analysis."""
    resume_text = _read_resume_text(payload.resume_name)
    try:
        suggestions = generate_resume_suggestions(
            resume_text,
            payload.jd_json,
            payload.gaps,
            override=payload.override,
            user_prompt=payload.user_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion generation failed: {e}")
    return {"suggestions": suggestions}


@router.post("/apply-suggestions")
async def apply_suggestions(payload: ApplySuggestionsIn):
    """Apply the user-approved suggestions to the original PDF and save a revised copy
    next to it in the uploads dir. Returns the revised filename + a download URL."""
    if not payload.accepted_changes:
        raise HTTPException(status_code=400, detail="No accepted changes provided")

    original_path = _resolve_resume_path(payload.resume_name)
    with open(original_path, "rb") as f:
        original_bytes = f.read()

    try:
        revised_bytes, report = apply_pdf_changes(
            original_bytes,
            [c.model_dump() for c in payload.accepted_changes],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF editing failed: {e}")

    base, ext = original_path.stem, original_path.suffix or ".pdf"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    revised_filename = f"{base}_revised_{timestamp}{ext}"
    revised_path = UPLOAD_DIR / revised_filename
    with open(revised_path, "wb") as f:
        f.write(revised_bytes)

    return {
        "revised_filename": revised_filename,
        "download_url": f"/api/analyze/download/{revised_filename}",
        "report": report,
    }


@router.get("/download/{resume_name}")
async def download_resume(resume_name: str):
    """Download a (revised) PDF — forces Content-Disposition: attachment."""
    file_path = _resolve_resume_path(resume_name)
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=resume_name,
        headers={"Content-Disposition": f'attachment; filename="{resume_name}"'},
    )
