"""Analysis routes (Postgres-backed).

Minimisation changes
--------------------
- /run now calls analyze_scorecard_and_suggestions() — ONE LLM call instead of two.
  Scorecard + suggestions are returned together and both saved to the DB.
- /suggestions is kept for explicit user-triggered regeneration (override/user_prompt).
  It calls the combined function with override=True or a user_prompt.
- verify_loop is NOT called automatically — only on explicit user request.
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import get_current_user
from auth_automation_api_key_dep import get_user_from_automation_api_key
from database import get_conn, db_get_active_provider
from launchpad.utils.parser import extract_text_from_pdf
from launchpad.utils.pdf_viewer import UPLOAD_DIR
from launchpad.utils.jd_extraction import extract_jd
from launchpad.utils.scorecard import analyze_scorecard_and_suggestions
from launchpad.utils.pdf_editor import apply_changes as apply_pdf_changes
from database import (
    db_get_goal_set, db_get_resume_by_filename,
    db_insert_analysis, db_upsert_suggestions,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Request models ────────────────────────────────────────────────────────────

class RunAnalysisIn(BaseModel):
    resume_name: str
    goal_set_id: str
    jd_text: Optional[str] = None
    jd_url: Optional[str] = None
    jd_link: Optional[str] = None  # Source URL for JD (from browser extension or URL import)


class SuggestionsIn(BaseModel):
    resume_name: str
    jd_json: Dict[str, Any]
    gaps: List[Any] = []
    user_prompt: Optional[str] = None
    override: bool = False


class AcceptedChange(BaseModel):
    type: str
    section: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None


class ApplySuggestionsIn(BaseModel):
    resume_name: str
    accepted_changes: List[AcceptedChange]


class ExtractJdUrlIn(BaseModel):
    url: str


class ExtractJdImageIn(BaseModel):
    image_base64: str
    media_type: str = "image/png"


# ── Helpers ───────────────────────────────────────────────────────────────────

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


async def _get_resume_text(resume_name: str, user_id: str) -> str:
    db_row = await db_get_resume_by_filename(resume_name, user_id=user_id)
    if db_row and db_row.get("extracted_text"):
        return db_row["extracted_text"]
    return extract_text_from_pdf(BytesIO(_read_resume_bytes(resume_name)))


def _resume_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


async def _ensure_exported_column() -> None:
    async with get_conn() as conn:
        await conn.execute(
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS exported BOOLEAN DEFAULT false"
        )


def deduce_contact_name(email: Optional[str]) -> Optional[str]:
    """
    Deduce a contact name from an email address.
    
    Rules:
    - If email local-part is a role alias (hr, careers, jobs, etc.), return None
    - Otherwise, extract first name from local-part (split on . _ -, take first, capitalize)
    
    Examples:
        john.doe@example.com -> "John"
        hr@example.com -> None
        j_smith@example.com -> "J"
    """
    if not email:
        return None
    
    email = email.strip().lower()
    # Extract local part (before @)
    if "@" not in email:
        return None
    
    local_part = email.split("@")[0]
    
    # Role aliases that shouldn't be used as names
    role_aliases = {
        "hr", "careers", "jobs", "info", "contact", "recruiting", "talent",
        "no-reply", "noreply", "admin", "team", "hiring", "recruitment",
        "support", "sales", "apply", "applications"
    }
    
    if local_part in role_aliases:
        return None
    
    # Split on common separators and get first part
    for sep in [".", "_", "-"]:
        if sep in local_part:
            first_part = local_part.split(sep)[0]
            break
    else:
        first_part = local_part
    
    # Clean up and capitalize
    first_name = first_part.strip()
    if not first_name:
        return None
    
    # Capitalize first letter, lowercase rest
    return first_name[0].upper() + first_name[1:].lower() if len(first_name) > 0 else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run")
async def run_analysis(payload: RunAnalysisIn, user: dict = Depends(get_current_user)):
    """Single combined LLM call: extract JD → score + suggestions together → save."""
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[ANALYSIS] POST /run request - User: {user_email} | Resume: {payload.resume_name} | Goal Set: {payload.goal_set_id}")
    
    if not (payload.jd_text or payload.jd_url):
        logger.warning(f"[ANALYSIS] ⚠ Missing JD - User: {user_email}")
        raise HTTPException(status_code=400, detail="Provide jd_text or jd_url")

    try:
        resume_text = await _get_resume_text(payload.resume_name, user_id)
        logger.debug(f"[ANALYSIS] ✓ Resume loaded - User: {user_email} | Resume: {payload.resume_name}")
    except Exception as e:
        logger.error(f"[ANALYSIS] ✗ Resume read failed - User: {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Resume read failed: {e}")

    goal_set = await db_get_goal_set(payload.goal_set_id, user_id=user_id)
    if not goal_set:
        logger.warning(f"[ANALYSIS] ⚠ Goal set not found - User: {user_email} | Goal Set: {payload.goal_set_id}")
        raise HTTPException(status_code=404, detail=f"Goal set {payload.goal_set_id} not found")

    goals = [
        {
            "id": g.get("id"),
            "label": g.get("label"),
            "description": g.get("description", ""),
            "confidence": g.get("confidence", "high"),
        }
        for g in goal_set.get("goals", [])
    ]
    
    logger.debug(f"[ANALYSIS] Goal set loaded - User: {user_email} | Goals: {len(goals)}")

    try:
        jd_json = extract_jd(payload.jd_text or "", payload.jd_url)
        logger.debug(f"[ANALYSIS] ✓ JD extracted - User: {user_email}")
    except Exception as e:
        logger.error(f"[ANALYSIS] ✗ JD extraction failed - User: {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"JD extraction failed: {e}")

    # Get active provider BEFORE calling LLM
    active_provider = await db_get_active_provider(user_id)
    logger.info(f"[LLM] Calling LLM for analysis - User: {user_email} | Active Provider: {active_provider}")
    
    # ONE combined LLM call — replaces scorecard() + suggestions() round-trip
    # Now also returns job_summary and my_relevance for outreach
    try:
        scorecard, suggestions, job_summary, my_relevance = analyze_scorecard_and_suggestions(
            resume_text, jd_json, goals
        )
        logger.info(f"[LLM] ✓ Analysis complete - User: {user_email} | Active Provider: {active_provider} | Verdict: {scorecard.verdict}")
    except Exception as e:
        logger.error(f"[LLM] ✗ LLM analysis failed - User: {user_email} | Active Provider: {active_provider}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    jd_id = str(uuid.uuid4())[:8]
    entry = {
        "jd_id": jd_id,
        "analyzed_at": datetime.now(),
        "goal_set_id": goal_set["id"],
        "goal_set_name": goal_set["name"],
        "goal_set_snapshot": goal_set.get("goals", []),
        "resume_id": payload.resume_name,
        "resume_snapshot_hash": _resume_hash(resume_text),
        "scorecard": scorecard.to_dict(),
        "jd_text": payload.jd_text,
        "jd_json": jd_json,
        "jd_link": payload.jd_link or None,  # Store the source URL if provided
        "job_summary": job_summary or None,  # 3-5 bullet points about the role
        "my_relevance": my_relevance or None,  # 3-5 bullet points on why candidate fits
        "verdict": scorecard.verdict,
        "overall_fit": scorecard.overall_fit,
        "status": "analysed",
        "changes_generated": True,
        "jd_title": jd_json.get("title", "?"),
        "company": jd_json.get("company", "?"),
        "url": jd_json.get("url"),
    }

    try:
        await db_insert_analysis(entry, user_id=user_id)
        await db_upsert_suggestions(jd_id, suggestions, user_id=user_id)
        logger.info(f"[ANALYSIS] ✓ Analysis saved - User: {user_email} | JD ID: {jd_id}")
    except Exception as e:
        logger.error(f"[ANALYSIS] ✗ DB save failed - User: {user_email}: {e}")

    response = {
        "jd_id": jd_id,
        "jd": jd_json,
        "scorecard": scorecard.to_dict(),
        "suggestions": suggestions,
        "resume_name": payload.resume_name,
        "goal_set_id": goal_set["id"],
        "goal_set_name": goal_set["name"],
    }
    
    logger.info(f"[ANALYSIS] ✓ POST /run response - User: {user_email} | Active Provider: {active_provider}")
    logger.debug(f"[ANALYSIS] Response keys: {list(response.keys())} | Verdict: {scorecard.verdict} | Overall Fit: {scorecard.overall_fit}")
    
    return response


@router.post("/suggestions")
async def get_suggestions(payload: SuggestionsIn, user: dict = Depends(get_current_user)):
    """Explicit suggestion regeneration — only called when user requests override or adds guidance."""
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[SUGGESTIONS] POST /suggestions request - User: {user_email} | Override: {payload.override} | Has user_prompt: {bool(payload.user_prompt)}")
    
    resume_text = await _get_resume_text(payload.resume_name, user_id)
    
    # Get active provider BEFORE calling LLM
    active_provider = await db_get_active_provider(user_id)
    logger.info(f"[LLM] Calling LLM for suggestions - User: {user_email} | Active Provider: {active_provider}")
    
    try:
        from launchpad.utils.scorecard import analyze_scorecard_and_suggestions
        _, suggestions, _, _ = analyze_scorecard_and_suggestions(
            resume_text,
            payload.jd_json,
            [],   # goals not needed for suggestions-only regen
            override=payload.override,
            user_prompt=payload.user_prompt,
        )
        logger.info(f"[LLM] ✓ Suggestions generated - User: {user_email} | Active Provider: {active_provider} | Count: {len(suggestions)}")
    except Exception as e:
        logger.error(f"[LLM] ✗ Suggestion generation failed - User: {user_email} | Active Provider: {active_provider}: {e}")
        raise HTTPException(status_code=500, detail=f"Suggestion generation failed: {e}")
    
    response = {"suggestions": suggestions}
    logger.debug(f"[SUGGESTIONS] Response: {len(suggestions)} suggestions generated")
    return response


@router.post("/extract-jd-url")
async def extract_jd_from_url(payload: ExtractJdUrlIn, user: dict = Depends(get_current_user)):
    import re
    try:
        import requests as req
        from bs4 import BeautifulSoup
    except ImportError:
        raise HTTPException(status_code=500, detail="requests / beautifulsoup4 not installed")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = req.get(payload.url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not fetch URL: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "iframe", "svg"]):
        tag.decompose()

    jd_text = ""
    for selector in ["[data-automation='jobDescription']", ".job-description", "#job-description",
                     "[class*='jobDescription']", "[class*='job-details']", "[class*='description']",
                     "article", "main"]:
        el = soup.select_one(selector)
        if el:
            jd_text = el.get_text(separator="\n", strip=True)
            if len(jd_text) > 200:
                break

    if len(jd_text) < 200:
        jd_text = soup.get_text(separator="\n", strip=True)
    jd_text = re.sub(r"\n{3,}", "\n\n", jd_text).strip()
    if len(jd_text) < 100:
        raise HTTPException(status_code=422, detail="Could not extract job description text from that URL.")
    return {"jd_text": jd_text[:12000]}


@router.post("/extract-jd-image")
async def extract_jd_from_image(payload: ExtractJdImageIn, user: dict = Depends(get_current_user)):
    import base64 as b64lib, io
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise HTTPException(status_code=500, detail="pytesseract / Pillow not installed.")
    try:
        img_bytes = b64lib.b64decode(payload.image_base64)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        jd_text = pytesseract.image_to_string(image, lang="eng", config="--psm 6").strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")
    if len(jd_text) < 50:
        raise HTTPException(status_code=422, detail="Could not extract enough text from the image.")
    return {"jd_text": jd_text}


@router.post("/apply-suggestions")
async def apply_suggestions(payload: ApplySuggestionsIn):
    if not payload.accepted_changes:
        raise HTTPException(status_code=400, detail="No accepted changes provided")
    original_path = _resolve_resume_path(payload.resume_name)
    with open(original_path, "rb") as f:
        original_bytes = f.read()
    try:
        revised_bytes, report = apply_pdf_changes(
            original_bytes, [c.model_dump() for c in payload.accepted_changes]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF editing failed: {e}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    revised_filename = f"{original_path.stem}_revised_{timestamp}{original_path.suffix or '.pdf'}"
    with open(UPLOAD_DIR / revised_filename, "wb") as f:
        f.write(revised_bytes)
    return {
        "revised_filename": revised_filename,
        "download_url": f"/api/analyze/download/{revised_filename}",
        "report": report,
    }


@router.get(
    "/pending-outreach",
    tags=["Automation"],
    summary="Get pending outreach items (n8n automation)",
    responses={
        200: {
            "description": "List of pending outreach analyses",
            "content": {
                "application/json": {
                    "example": {
                        "pending": [
                            {
                                "jd_id": "uuid-of-analysis",
                                "jd_title": "Senior Software Engineer",
                                "company": "Acme Corp",
                                "verified_email": "hiring@acme.com",
                                "recipient_type": "hiring-manager",
                                "contact_name": "John Smith",
                                "overall_fit": 8.5,
                                "verdict": "apply"
                            }
                        ]
                    }
                }
            }
        },
        401: {
            "description": "Invalid or missing X-API-Key header",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid or inactive automation API key"}
                }
            }
        }
    }
)
async def pending_outreach(user: dict = Depends(get_user_from_automation_api_key)):
    """
    Get pending outreach items (called by n8n automation via X-API-Key header).
    
    **Authentication:** X-API-Key header (NOT Bearer token)
    
    **Headers Required:**
    - `X-API-Key: <your-api-key>`
    
    **Example curl:**
    ```bash
    curl -X GET 'http://localhost:8000/api/analyze/pending-outreach' \
      -H 'accept: application/json' \
      -H 'X-API-Key: AbCdEfGhIjKlMnOpQrStUvWxYz123456'
    ```
    
    **Response:** List of analyses with verdict 'apply' or 'borderline' that haven't been exported yet.
    
    **CRITICAL SECURITY:**
    - Scoped to the authenticated user via the API key
    - User lookup is server-side (never from request parameters)
    - Only returns analyses belonging to the API key owner
    - Invalid/inactive keys return 401 Unauthorized
    
    **For n8n Integration:**
    1. Generate API key: POST /api/settings/automation-api-keys (requires JWT)
    2. Store in n8n vault: Settings → Vault → LAUNCHPAD_API_KEY
    3. Use in HTTP Request node: Header X-API-Key = {{ $secret.LAUNCHPAD_API_KEY }}
    4. Call this endpoint to get pending analyses
    """
    await _ensure_exported_column()
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT jd_id, jd_title, company, jd_text, jd_url, jd_link, jd_json, 
                   scorecard, overall_fit, verdict, job_summary, my_relevance
            FROM analyses
            WHERE user_id = %s::uuid
              AND verdict IN ('apply', 'borderline')
              AND COALESCE(exported, false) = false
            ORDER BY analyzed_at DESC
            """,
            (str(user["id"]),),
        )
        rows = await cur.fetchall()
        pending = []
        for row in rows:
            item = dict(row)
            jd_json = item.get("jd_json") or {}
            if isinstance(jd_json, str):
                try:
                    jd_json = json.loads(jd_json)
                except Exception:
                    jd_json = {}

            if isinstance(jd_json, dict):
                verified_email = jd_json.get("verified_email")
                recipient_type = jd_json.get("recipient_type")
                contact_name = jd_json.get("contact_name")
            else:
                verified_email = None
                recipient_type = None
                contact_name = None

            jd_text = item.get("jd_text") or ""
            if not verified_email:
                m = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", jd_text, re.IGNORECASE)
                if m:
                    verified_email = m.group(0).strip()
            if not recipient_type:
                lowered = jd_text.lower()
                if "recruiter" in lowered or "talent partner" in lowered:
                    recipient_type = "recruiter"
                elif "hiring manager" in lowered:
                    recipient_type = "hiring_manager"
                elif "hr" in lowered:
                    recipient_type = "hr"
            if not contact_name:
                m = re.search(r"(?:contact|hi)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", jd_text)
                if m:
                    contact_name = m.group(1).strip()

            jd_url = item.get("jd_url") or item.get("url") or ""
            if not jd_url and isinstance(jd_json, dict):
                jd_url = jd_json.get("url") or ""
            if not jd_url and isinstance(item.get("jd_json"), dict):
                jd_url = item["jd_json"].get("url") or ""

            company = item.get("company") or ""
            role = item.get("jd_title") or ""
            if not company and isinstance(jd_json, dict):
                company = jd_json.get("company") or ""
            if not role and isinstance(jd_json, dict):
                role = jd_json.get("title") or ""

            jd_summary_parts = []
            if isinstance(jd_json, dict):
                jd_summary_parts.extend(
                    part for part in [
                        jd_json.get("domain"),
                        jd_json.get("location_policy"),
                        jd_json.get("seniority"),
                        jd_json.get("title"),
                        jd_json.get("company"),
                    ] if part
                )

            jd_summary = " | ".join(dict.fromkeys(jd_summary_parts)) if jd_summary_parts else ""

            scorecard = item.get("scorecard") or {}
            if isinstance(scorecard, str):
                try:
                    scorecard = json.loads(scorecard)
                except Exception:
                    scorecard = {}

            # Get job_summary from DB (3-5 bullet points about the role)
            job_summary_bullets = item.get("job_summary")
            if isinstance(job_summary_bullets, str):
                try:
                    job_summary_bullets = json.loads(job_summary_bullets)
                except Exception:
                    job_summary_bullets = []
            if not isinstance(job_summary_bullets, list):
                job_summary_bullets = []

            # Get my_relevance from DB (3-5 bullet points on candidate fit)
            my_relevance_bullets = item.get("my_relevance")
            if isinstance(my_relevance_bullets, str):
                try:
                    my_relevance_bullets = json.loads(my_relevance_bullets)
                except Exception:
                    my_relevance_bullets = []
            if not isinstance(my_relevance_bullets, list):
                my_relevance_bullets = []

            # Get jd_link from DB (source URL of the JD, may be null for pasted text)
            jd_link = item.get("jd_link") or None

            # Deduce contact name from email if not set and email exists
            deduced_name = deduce_contact_name(verified_email) if verified_email else None
            final_contact_name = contact_name or deduced_name or None

            outreach_item = {
                "id": item.get("jd_id"),
                "contact_name": final_contact_name,
                "verified_email": verified_email or None,
                "recipient_type": recipient_type or None,
                "jd_link": jd_link,
                "company": company,
                "role": role,
                "jd_summary": job_summary_bullets,  # Array of bullets from LLM
                "my_relevance": my_relevance_bullets,  # Array of bullets from LLM
                "last_reply": "",
                "followup_count": 0,
                "status": "needs_contact",
                "thread_id": "",
                "last_message_sent": "",
                "next_action_date": "",
            }
            pending.append(outreach_item)
        return pending


@router.post(
    "/pending-outreach/{jd_id}/mark-exported",
    tags=["Automation"],
    summary="Mark analysis as exported (n8n automation)",
    responses={
        200: {
            "description": "Successfully marked as exported",
            "content": {
                "application/json": {
                    "example": {"ok": True}
                }
            }
        },
        401: {
            "description": "Invalid or missing X-API-Key header",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid or inactive automation API key"}
                }
            }
        },
        404: {
            "description": "Analysis not found or doesn't belong to authenticated user",
            "content": {
                "application/json": {
                    "example": {"detail": "Analysis abc-123 not found or does not belong to this user"}
                }
            }
        }
    }
)
async def mark_exported(jd_id: str, user: dict = Depends(get_user_from_automation_api_key)):
    """
    Mark a pending outreach item as exported (called by n8n automation via X-API-Key header).
    
    **Authentication:** X-API-Key header (NOT Bearer token)
    
    **Headers Required:**
    - `X-API-Key: <your-api-key>`
    
    **Path Parameters:**
    - `jd_id`: UUID of the analysis to mark as exported
    
    **Example curl:**
    ```bash
    curl -X POST 'http://localhost:8000/api/analyze/pending-outreach/abc-123-uuid/mark-exported' \
      -H 'accept: application/json' \
      -H 'X-API-Key: AbCdEfGhIjKlMnOpQrStUvWxYz123456'
    ```
    
    **Response:** `{"ok": true}` on success
    
    **Errors:**
    - 401: Invalid/missing API key
    - 404: Analysis not found or doesn't belong to the API key owner
    
    **CRITICAL SECURITY:**
    - Only marks analyses belonging to the authenticated user
    - Prevents users from marking other users' analyses as exported
    - Returns 404 if jd_id doesn't belong to the API key owner (not 403, prevents enumeration attacks)
    
    **Typical n8n Workflow:**
    1. GET /api/analyze/pending-outreach (get list of pending analyses)
    2. For each analysis:
       - Send outreach email or message
       - POST /pending-outreach/{jd_id}/mark-exported (mark as done)
    """
    await _ensure_exported_column()
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE analyses SET exported = true WHERE jd_id = %s AND user_id = %s::uuid",
            (jd_id, str(user["id"])),
        )
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {jd_id} not found or does not belong to this user",
            )
    return {"ok": True}


@router.get("/download/{resume_name}")
async def download_resume(resume_name: str, user: dict = Depends(get_current_user)):
    """Download a resume file. Scoped to the authenticated user."""
    # Verify the resume belongs to this user before serving it
    db_resume = await db_get_resume_by_filename(resume_name, user_id=str(user["id"]))
    if not db_resume:
        raise HTTPException(status_code=404, detail=f"Resume {resume_name} not found")
    
    file_path = _resolve_resume_path(resume_name)
    return FileResponse(
        path=str(file_path), media_type="application/pdf", filename=resume_name,
        headers={"Content-Disposition": f'attachment; filename="{resume_name}"'},
    )