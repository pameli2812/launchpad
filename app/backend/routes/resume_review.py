"""Resume Review routes — LLM-extracted structured profile per resume.

Routes are scoped to the current user via Depends(get_current_user). The
extract route also loads per-user LLM API keys (Settings page) into the
contextvar via Depends(load_user_llm_keys), so user-set keys take precedence
over the server's env keys.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import (
    db_delete_resume_review,
    db_get_resume_by_filename,
    db_get_resume_review_by_resume_id,
    db_patch_resume_review,
    db_upsert_resume_review,
)
from launchpad.utils.parser import extract_text_from_pdf
from launchpad.utils.pdf_viewer import UPLOAD_DIR
from launchpad.utils.resume_review import extract_resume_profile
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


# ── Read ─────────────────────────────────────────────────────────────────────

@router.get("/{resume_name}")
async def get_review(
    resume_name: str,
    user: dict = Depends(get_current_user),
):
    """Return the cached review if one exists, else 404 (UI then shows
    'Run review' button)."""
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    review = await db_get_resume_review_by_resume_id(str(db_resume["id"]), str(user["id"]))
    if not review:
        raise HTTPException(status_code=404, detail="No review yet")
    return {"review": review}


# ── Run extraction ───────────────────────────────────────────────────────────

@router.post("/{resume_name}/extract")
async def extract_review(
    resume_name: str,
    user: dict = Depends(get_current_user),
    _keys: None = Depends(load_user_llm_keys),
):
    """Run (or re-run) the LLM extraction for this resume. Persists the result;
    subsequent GETs return it without another LLM call."""
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Prefer the text we already extracted at upload time; fall back to
    # re-parsing the PDF only if the DB row is missing it for some reason.
    resume_text = db_resume.get("extracted_text")
    if not resume_text:
        path = _resolve_resume_path(resume_name)
        with open(path, "rb") as f:
            resume_text = extract_text_from_pdf(BytesIO(f.read()))

    if not resume_text or len(resume_text) < 100:
        raise HTTPException(
            status_code=422,
            detail="Resume text too short to extract a profile from",
        )

    try:
        profile = extract_resume_profile(resume_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")

    review = await db_upsert_resume_review(
        user_id=str(user["id"]),
        resume_id=str(db_resume["id"]),
        review=profile,
    )
    return {"review": review, "message": "extracted"}


# ── Edit ─────────────────────────────────────────────────────────────────────

class ReviewPatch(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: list | None = None
    experience: list | None = None
    education: list | None = None
    certifications: list | None = None
    projects: list | None = None


@router.patch("/{resume_name}")
async def patch_review(
    resume_name: str,
    patch: ReviewPatch,
    user: dict = Depends(get_current_user),
):
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Only forward keys the user actually sent (model_dump(exclude_unset=True)
    # — Pydantic v2 semantics: leaves out fields the client didn't include)
    patch_dict = patch.model_dump(exclude_unset=True)
    if not patch_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await db_patch_resume_review(str(db_resume["id"]), str(user["id"]), patch_dict)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="No review to patch — run /extract first",
        )
    return {"review": updated}


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{resume_name}")
async def delete_review(
    resume_name: str,
    user: dict = Depends(get_current_user),
):
    db_resume = await db_get_resume_by_filename(resume_name)
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    deleted = await db_delete_resume_review(str(db_resume["id"]), str(user["id"]))
    if not deleted:
        raise HTTPException(status_code=404, detail="No review to delete")
    return {"message": "review deleted"}
