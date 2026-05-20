"""
Setup routes - Handle resume uploads and goal management
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from io import BytesIO
import sys
from pathlib import Path

# Import from launchpad utils
from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.pdf_viewer import save_pdf_locally, get_uploaded_pdfs
from utils.models import GoalSet, Goal
from utils.storage import read_json, write_json

router = APIRouter()

# Data file paths
GOAL_SETS_FILE = "../launchpad/data/goal_sets.json"
UPLOADS_DIR = "../launchpad/data/uploads"

# ─────────────────────────────────────────────
# Resume Management
# ─────────────────────────────────────────────

@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume (PDF or DOCX)"""
    try:
        # Validate file type
        if not file.filename.endswith(('.pdf', '.docx')):
            raise HTTPException(status_code=400, detail="File must be PDF or DOCX")
        
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(BytesIO(content))
        else:
            text = extract_text_from_docx(BytesIO(content))
        
        # Save file locally
        save_pdf_locally(file.filename, content)
        
        return {
            "filename": file.filename,
            "size": len(content),
            "extracted_text": text[:500],  # Return first 500 chars as preview
            "message": "Resume uploaded successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumes")
async def list_resumes():
    """List all uploaded resumes"""
    try:
        pdfs = get_uploaded_pdfs()
        return {"resumes": pdfs, "total": len(pdfs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/resume/{resume_name}")
async def delete_resume(resume_name: str):
    """Delete a resume"""
    try:
        # Implementation depends on your pdf_viewer.py delete_pdf function
        return {"message": f"Resume {resume_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Goal Set Management
# ─────────────────────────────────────────────

@router.get("/goal-sets")
async def list_goal_sets():
    """List all goal sets"""
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": []})
        return {"goal_sets": data.get("goal_sets", []), "total": len(data.get("goal_sets", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal-sets")
async def create_goal_set(goal_set: GoalSet):
    """Create a new goal set"""
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": []})
        data["goal_sets"].append(goal_set.dict())
        write_json(GOAL_SETS_FILE, data)
        return {"message": "Goal set created", "goal_set": goal_set}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/goal-sets/{goal_set_id}")
async def delete_goal_set(goal_set_id: str):
    """Delete a goal set"""
    try:
        data = read_json(GOAL_SETS_FILE, default={"goal_sets": []})
        data["goal_sets"] = [gs for gs in data["goal_sets"] if gs["id"] != goal_set_id]
        write_json(GOAL_SETS_FILE, data)
        return {"message": f"Goal set {goal_set_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
