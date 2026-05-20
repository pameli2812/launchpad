"""
History routes - Handle analysis history and data persistence
"""

from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

# Import from launchpad utils
from utils.models import HistoryEntry
from utils.storage import read_json, write_json

router = APIRouter()

HISTORY_FILE = "../launchpad/data/history.json"

# ─────────────────────────────────────────────
# History Management
# ─────────────────────────────────────────────

@router.get("/")
async def get_history():
    """Get all history entries"""
    try:
        history = read_json(HISTORY_FILE, default=[])
        return {
            "history": history,
            "total": len(history),
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entry_id}")
async def get_history_entry(entry_id: str):
    """Get a specific history entry"""
    try:
        history = read_json(HISTORY_FILE, default=[])
        entry = next((h for h in history if h.get("id") == entry_id), None)
        
        if not entry:
            raise HTTPException(status_code=404, detail="History entry not found")
        
        return {
            "entry": entry,
            "status": "success",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def add_history_entry(entry: HistoryEntry):
    """Add a new entry to history"""
    try:
        history = read_json(HISTORY_FILE, default=[])
        history.append(entry.dict())
        write_json(HISTORY_FILE, history)
        
        return {
            "entry": entry,
            "message": "History entry saved",
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_history_entry(entry_id: str):
    """Delete a history entry"""
    try:
        history = read_json(HISTORY_FILE, default=[])
        history = [h for h in history if h.get("id") != entry_id]
        write_json(HISTORY_FILE, history)
        
        return {
            "message": f"History entry {entry_id} deleted",
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{entry_id}/suggestions")
async def save_suggestions(entry_id: str, suggestions: dict):
    """Save suggestions to a history entry"""
    try:
        history = read_json(HISTORY_FILE, default=[])
        entry = next((h for h in history if h.get("id") == entry_id), None)
        
        if not entry:
            raise HTTPException(status_code=404, detail="History entry not found")
        
        entry["suggestions"] = suggestions
        entry["suggestions_generated_at"] = datetime.now().isoformat()
        
        write_json(HISTORY_FILE, history)
        
        return {
            "entry": entry,
            "message": "Suggestions saved",
            "status": "success",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
