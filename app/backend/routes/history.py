"""History routes (Postgres-backed)."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from database import db_list_analyses, db_delete_analysis, db_upsert_suggestions

router = APIRouter()


@router.get("/")
async def get_history(user: dict = Depends(get_current_user)):
    try:
        history = await db_list_analyses(str(user["id"]))
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_history_entry(entry_id: str, user: dict = Depends(get_current_user)):
    try:
        deleted = await db_delete_analysis(entry_id, str(user["id"]))
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
        return {"message": f"Entry {entry_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{entry_id}/suggestions")
async def save_suggestions(entry_id: str, suggestions: Dict[str, Any], user: dict = Depends(get_current_user)):
    try:
        saved = await db_upsert_suggestions(entry_id, suggestions, str(user["id"]))
        if not saved:
            raise HTTPException(status_code=404, detail=f"Analysis {entry_id} not found")
        return {"message": "Suggestions saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))