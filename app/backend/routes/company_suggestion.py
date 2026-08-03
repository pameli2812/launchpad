"""Company Suggestion routes — LLM-curated target-company list per resume."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import (
    db_delete_company_suggestion,
    db_get_company_suggestion,
    db_get_resume_by_filename,
    db_upsert_company_suggestion,
)
from launchpad.utils.company_suggestion import suggest_companies
from launchpad.utils.parser import extract_text_from_pdf
from launchpad.utils.pdf_viewer import UPLOAD_DIR
from llm_keys_dep import load_user_llm_keys

router = APIRouter()


def _resolve_resume_path(resume_name: str) -> Path:
    candidate = (UPLOAD_DIR / resume_name).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if upload_root not in candidate.parents and candidate != upload_root:
        raise HTTPException(status_code=400, detail="Invalid resume filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    return candidate


class GenerateIn(BaseModel):
    user_prompt: str | None = None


# ── Read ─────────────────────────────────────────────────────────────────────

@router.get("/{resume_name}")
async def get_suggestion(
    resume_name: str,
    user: dict = Depends(get_current_user),
):
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    suggestion = await db_get_company_suggestion(str(db_resume["id"]), str(user["id"]))
    if not suggestion:
        raise HTTPException(status_code=404, detail="No suggestions yet")
    return {"suggestion": suggestion}


# ── Generate ─────────────────────────────────────────────────────────────────

@router.post("/{resume_name}/generate")
async def generate_suggestion(
    resume_name: str,
    payload: GenerateIn,
    user: dict = Depends(get_current_user),
    _keys: None = Depends(load_user_llm_keys),
):
    """Run (or re-run) company suggestion for this resume. Persists the result
    so subsequent GETs skip the LLM. user_prompt is optional preference text."""
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume_text = db_resume.get("extracted_text")
    if not resume_text:
        path = _resolve_resume_path(resume_name)
        with open(path, "rb") as f:
            resume_text = extract_text_from_pdf(BytesIO(f.read()))

    if not resume_text or len(resume_text) < 100:
        raise HTTPException(
            status_code=422,
            detail="Resume text too short to suggest companies from",
        )

    try:
        result = suggest_companies(resume_text, user_prompt=payload.user_prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Suggestion failed: {e}")

    saved = await db_upsert_company_suggestion(
        user_id=str(user["id"]),
        resume_id=str(db_resume["id"]),
        companies=result.get("companies", []),
        user_prompt=payload.user_prompt,
        raw=result.get("raw"),
    )
    return {"suggestion": saved, "message": "generated"}


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{resume_name}")
async def delete_suggestion(
    resume_name: str,
    user: dict = Depends(get_current_user),
):
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    deleted = await db_delete_company_suggestion(str(db_resume["id"]), str(user["id"]))
    if not deleted:
        raise HTTPException(status_code=404, detail="No suggestion to delete")
    return {"message": "deleted"}
