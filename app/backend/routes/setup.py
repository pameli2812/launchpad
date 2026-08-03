"""Setup routes — resume uploads and goal management (Postgres-backed)."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List, Optional
from io import BytesIO
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
import hashlib

from launchpad.utils.parser import extract_text_from_pdf, extract_text_from_docx
from launchpad.utils.pdf_viewer import save_pdf_locally, get_uploaded_pdfs, delete_pdf, UPLOAD_DIR
from launchpad.utils.goal_inference import auto_infer_goals_from_resume
from auth import get_current_user
from database import (
    db_insert_resume, db_list_resumes, db_get_resume_by_filename,
    db_delete_resume, db_list_goal_sets, db_get_goal_set,
    db_insert_goal_set, db_delete_goal_set,
    db_activate_goal_set, db_deactivate_goal_set,
)

router = APIRouter()


def _resolve_resume_path(resume_name: str) -> Path:
    candidate = (UPLOAD_DIR / resume_name).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if upload_root not in candidate.parents and candidate != upload_root:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    return candidate


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


# ── Resume Management ─────────────────────────────────────────────────────────

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    try:
        if not file.filename.endswith(('.pdf', '.docx')):
            raise HTTPException(status_code=400, detail="File must be PDF or DOCX")

        content = await file.read()

        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(BytesIO(content))
        else:
            text = extract_text_from_docx(BytesIO(content))

        saved_path = save_pdf_locally(content, file.filename)
        saved_filename = Path(saved_path).name
        content_hash = hashlib.sha256(content).hexdigest()[:12]

        await db_insert_resume(
            user_id=str(user["id"]),
            filename=saved_filename,
            original_name=file.filename,
            size_bytes=len(content),
            content_hash=content_hash,
            extracted_text=text,
        )

        return {
            "filename": saved_filename,
            "size": len(content),
            "extracted_text": text[:500],
            "message": "Resume uploaded successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumes")
async def list_resumes(user: dict = Depends(get_current_user)):
    try:
        resumes = await db_list_resumes(str(user["id"]))
        # Normalise to the shape the frontend expects
        result = [
            {
                "name": r["filename"],
                "size": r["size_bytes"],
                "modified": r["uploaded_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("uploaded_at") else "",
            }
            for r in resumes
        ]
        return {"resumes": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resume/{resume_name}/view")
async def view_resume(resume_name: str, user: dict = Depends(get_current_user)):
    db_resume = await db_get_resume_by_filename(resume_name, user_id=str(user["id"]))
    if not db_resume:
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    file_path = _resolve_resume_path(resume_name)
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=resume_name,
        headers={"Content-Disposition": f'inline; filename="{resume_name}"'},
    )


@router.delete("/resume/{resume_name}")
async def delete_resume(resume_name: str, user: dict = Depends(get_current_user)):
    try:
        file_path = _resolve_resume_path(resume_name)
    except HTTPException as e:
        if e.status_code == 404:
            deleted = await db_delete_resume(resume_name, str(user["id"]))
            if not deleted:
                raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
            return {"message": f"Resume {resume_name} deleted"}
        raise

    try:
        if file_path.exists():
            delete_pdf(str(file_path))
        deleted = await db_delete_resume(resume_name, str(user["id"]))
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
        return {"message": f"Resume {resume_name} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Goal Set Management ───────────────────────────────────────────────────────

@router.get("/goal-sets")
async def list_goal_sets(user: dict = Depends(get_current_user)):
    try:
        goal_sets = await db_list_goal_sets(str(user["id"]))
        return {"goal_sets": goal_sets, "total": len(goal_sets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets")
async def create_goal_set(goal_set: GoalSetIn, user: dict = Depends(get_current_user)):
    try:
        gs = await db_insert_goal_set(
            user_id=str(user["id"]),
            goal_set_id=goal_set.id,   # passed through but not used as PK anymore
            name=goal_set.name,
            goals=[g.model_dump() for g in goal_set.goals],
        )
        # gs["id"] is now the real Postgres UUID — frontend must use this for
        # activate/delete calls from this point on.
        return {"message": "Goal set created", "goal_set": gs}
    except Exception as e:
        print(f"[setup] create_goal_set error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/goal-sets/{goal_set_id}")
async def delete_goal_set(goal_set_id: str, user: dict = Depends(get_current_user)):
    try:
        deleted = await db_delete_goal_set(goal_set_id, str(user["id"]))
        if not deleted:
            raise HTTPException(status_code=404, detail="Goal set not found")
        return {"message": f"Goal set {goal_set_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets/{goal_set_id}/activate")
async def activate_goal_set(goal_set_id: str, user: dict = Depends(get_current_user)):
    try:
        ok = await db_activate_goal_set(goal_set_id, str(user["id"]))
        if not ok:
            raise HTTPException(status_code=404, detail="Goal set not found")
        return {"message": f"Goal set {goal_set_id} activated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets/{goal_set_id}/deactivate")
async def deactivate_goal_set(goal_set_id: str, user: dict = Depends(get_current_user)):
    try:
        await db_deactivate_goal_set(goal_set_id, str(user["id"]))
        return {"message": f"Goal set {goal_set_id} deactivated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets/auto-infer")
async def auto_infer_goal_set(payload: AutoInferIn, user: dict = Depends(get_current_user)):
    file_path = _resolve_resume_path(payload.resume_name)
    try:
        # Try to get extracted text from DB first (avoids re-parsing the PDF)
        db_resume = await db_get_resume_by_filename(payload.resume_name, user_id=str(user["id"]))
        if db_resume and db_resume.get("extracted_text"):
            resume_text = db_resume["extracted_text"]
        else:
            with open(file_path, "rb") as f:
                resume_text = extract_text_from_pdf(BytesIO(f.read()))

        combined = resume_text
        if payload.context and payload.context.strip():
            combined += "\n\nAdditional preferences:\n" + payload.context.strip()

        # Pass the content_hash so repeated calls for the same resume are cached
        content_hash = db_resume.get("content_hash") if db_resume else None
        goals = auto_infer_goals_from_resume(combined, content_hash=content_hash)
        return {"goals": goals, "resume_name": payload.resume_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))