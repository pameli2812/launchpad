"""
Setup routes - Handle resume uploads and goal management
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List, Optional
from io import BytesIO
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

from launchpad.utils.parser import extract_text_from_pdf, extract_text_from_docx
from launchpad.utils.pdf_viewer import (
    save_pdf_locally,
    get_uploaded_pdfs,
    delete_pdf,
    UPLOAD_DIR,
)
from launchpad.utils.storage import read_json, write_json
from launchpad.utils.goal_inference import auto_infer_goals_from_resume

router = APIRouter()

# Absolute path so it works regardless of the working directory uvicorn is launched from.
# routes/setup.py -> routes/ -> backend/ -> app/ -> project root -> launchpad/data/goal_sets.json
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOAL_SETS_FILE = str(_PROJECT_ROOT / "launchpad" / "data" / "goal_sets.json")


def _resolve_resume_path(resume_name: str) -> Path:
    """Resolve a resume filename to an absolute path under UPLOAD_DIR,
    rejecting any path traversal attempts."""
    candidate = (UPLOAD_DIR / resume_name).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if upload_root not in candidate.parents and candidate != upload_root:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    return candidate


# ─────────────────────────────────────────────
# Pydantic request models (FastAPI needs these)
# ─────────────────────────────────────────────

class GoalIn(BaseModel):
    id: str
    label: str
    description: str
    confidence: str = "high"
    auto_inferred: bool = False

class GoalSetIn(BaseModel):
    id: str
    name: str
    goals: List[GoalIn]
    is_active: bool = False

class AutoInferIn(BaseModel):
    resume_name: str
    context: Optional[str] = None


# ─────────────────────────────────────────────
# Resume Management
# ─────────────────────────────────────────────

@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(('.pdf', '.docx')):
            raise HTTPException(status_code=400, detail="File must be PDF or DOCX")

        content = await file.read()

        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(BytesIO(content))
        else:
            text = extract_text_from_docx(BytesIO(content))

        # FIXED: correct argument order — bytes first, filename second
        save_pdf_locally(content, file.filename)

        return {
            "filename": file.filename,
            "size": len(content),
            "extracted_text": text[:500],
            "message": "Resume uploaded successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumes")
async def list_resumes():
    try:
        pdfs = get_uploaded_pdfs()
        return {"resumes": pdfs, "total": len(pdfs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resume/{resume_name}/view")
async def view_resume(resume_name: str):
    """Stream the PDF inline so the browser can render it."""
    file_path = _resolve_resume_path(resume_name)
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=resume_name,
        headers={"Content-Disposition": f'inline; filename="{resume_name}"'},
    )


@router.delete("/resume/{resume_name}")
async def delete_resume(resume_name: str):
    file_path = _resolve_resume_path(resume_name)
    try:
        delete_pdf(str(file_path))
        return {"message": f"Resume {resume_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Goal Set Management
# ─────────────────────────────────────────────

@router.get("/goal-sets")
async def list_goal_sets():
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": []})
        return {"goal_sets": data.get("goal_sets", []), "total": len(data.get("goal_sets", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets")
async def create_goal_set(goal_set: GoalSetIn):
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": [], "active_goal_set_id": None})
        payload = goal_set.model_dump()
        payload.setdefault("created_at", datetime.now().isoformat())
        payload["is_active"] = False  # new sets start inactive; user activates explicitly
        data.setdefault("goal_sets", []).append(payload)
        write_json(GOAL_SETS_FILE, data)
        return {"message": "Goal set created", "goal_set": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/goal-sets/{goal_set_id}")
async def delete_goal_set(goal_set_id: str):
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": [], "active_goal_set_id": None})
        data["goal_sets"] = [gs for gs in data.get("goal_sets", []) if gs["id"] != goal_set_id]
        if data.get("active_goal_set_id") == goal_set_id:
            data["active_goal_set_id"] = None
        write_json(GOAL_SETS_FILE, data)
        return {"message": f"Goal set {goal_set_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets/{goal_set_id}/activate")
async def activate_goal_set(goal_set_id: str):
    data = read_json(GOAL_SETS_FILE, default={"goal_sets": [], "active_goal_set_id": None})
    found = False
    for gs in data.get("goal_sets", []):
        if gs["id"] == goal_set_id:
            gs["is_active"] = True
            found = True
        else:
            gs["is_active"] = False
    if not found:
        raise HTTPException(status_code=404, detail="Goal set not found")
    data["active_goal_set_id"] = goal_set_id
    write_json(GOAL_SETS_FILE, data)
    return {"message": f"Goal set {goal_set_id} activated"}


@router.post("/goal-sets/{goal_set_id}/deactivate")
async def deactivate_goal_set(goal_set_id: str):
    data = read_json(GOAL_SETS_FILE, default={"goal_sets": [], "active_goal_set_id": None})
    for gs in data.get("goal_sets", []):
        if gs["id"] == goal_set_id:
            gs["is_active"] = False
    if data.get("active_goal_set_id") == goal_set_id:
        data["active_goal_set_id"] = None
    write_json(GOAL_SETS_FILE, data)
    return {"message": f"Goal set {goal_set_id} deactivated"}


@router.post("/goal-sets/auto-infer")
async def auto_infer_goal_set(payload: AutoInferIn):
    """Infer 5–7 candidate goals from a previously uploaded resume.
    Returns suggestions only — the client must POST /goal-sets to persist them."""
    file_path = _resolve_resume_path(payload.resume_name)
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        resume_text = extract_text_from_pdf(BytesIO(pdf_bytes))
        combined = resume_text
        if payload.context and payload.context.strip():
            combined += "\n\nAdditional preferences:\n" + payload.context.strip()
        goals = auto_infer_goals_from_resume(combined)
        return {"goals": goals, "resume_name": payload.resume_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))