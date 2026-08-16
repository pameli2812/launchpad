"""Imports routes — the browser extension's POST endpoint + the Analyze
page's read/consume endpoints.

Auth scheme is split intentionally:
  - POST /api/imports          authenticated via X-Launchpad-Extension-Token
                               (long-lived, generated in Settings, pasted into the
                                extension once)
  - GET / POST consume / etc.  authenticated via the SPA's JWT cookie

This keeps the extension a third-party client of the API rather than baking
its auth into the same JWT cookie flow the SPA uses.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from auth import get_current_user
from auth.deps import get_user_from_extension_token
from database import (
    db_insert_import,
    db_list_pending_imports,
    db_set_import_status,
)

router = APIRouter()


class ImportIn(BaseModel):
    """Payload from the browser extension."""

    jd_text: str
    url: str | None = None
    jd_title: str | None = None

    @field_validator("jd_text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 100:
            raise ValueError("jd_text looks too short to be a real job description")
        # Cap at 50K chars — anything longer is almost certainly the whole page,
        # not just the JD, and would blow the LLM context budget downstream.
        return v[:50_000]


def _host_and_job_id(url: str | None) -> tuple[str | None, str | None]:
    """Best-effort host + job id extraction from common ATS URLs."""
    if not url:
        return None, None
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except Exception:
        return None, None
    # Common ATS patterns: LinkedIn /jobs/view/3823..., Greenhouse /jobs/123456,
    # Lever /lever-co/.../<uuid>, Workday /job/.../<id>, Indeed jk=<id>
    job_id: str | None = None
    patterns = [
        r"/jobs?/view/(\d+)",                            # LinkedIn
        r"/jobs?/(\d+)",                                  # Greenhouse + many ATSs
        r"/job/[^/]+/[^/]+_([A-Za-z0-9-]+)",              # Workday
        r"[?&]jk=([A-Za-z0-9]+)",                         # Indeed
        r"/([A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12})",  # generic UUID
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            job_id = m.group(1)
            break
    return host, job_id


# ── Extension-facing endpoint ─────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def post_import(
    payload: ImportIn,
    user: dict = Depends(get_user_from_extension_token),
):
    """Receive a JD from the browser extension. Returns the created import row;
    the extension shows a 'Imported into Launchpad' success state."""
    host, job_id = _host_and_job_id(payload.url)
    row = await db_insert_import(
        user_id=str(user["id"]),
        jd_text=payload.jd_text,
        url=payload.url,
        host=host,
        job_id=job_id,
        jd_title=payload.jd_title,
    )
    return {"import": row, "message": "imported"}


# ── SPA-facing endpoints ──────────────────────────────────────────────────────

@router.get("/pending")
async def list_pending(user: dict = Depends(get_current_user)):
    """List the current user's pending imports, newest first."""
    rows = await db_list_pending_imports(str(user["id"]))
    return {"imports": rows}


@router.post("/{import_id}/consume")
async def consume(import_id: str, user: dict = Depends(get_current_user)):
    """Mark an import as consumed — called when the Analyze form successfully
    pulls the JD into its inputs."""
    ok = await db_set_import_status(str(user["id"]), import_id, "consumed")
    if not ok:
        raise HTTPException(status_code=404, detail="import not found")
    return {"message": "consumed"}


@router.post("/{import_id}/dismiss")
async def dismiss(import_id: str, user: dict = Depends(get_current_user)):
    """Mark an import as dismissed — user clicked the × on the banner."""
    ok = await db_set_import_status(str(user["id"]), import_id, "dismissed")
    if not ok:
        raise HTTPException(status_code=404, detail="import not found")
    return {"message": "dismissed"}
