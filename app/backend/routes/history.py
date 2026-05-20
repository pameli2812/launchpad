"""History routes — list, delete, and update saved analyses."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from launchpad.utils.storage import read_json, write_json

router = APIRouter()

# Anchored absolute path so React + Streamlit share the same history file
# regardless of where uvicorn is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HISTORY_FILE = str(_PROJECT_ROOT / "launchpad" / "data" / "history.json")


def _load() -> list:
    data = read_json(HISTORY_FILE, default=[]) or []
    return data if isinstance(data, list) else []


@router.get("/")
async def get_history():
    try:
        # Most recent first
        history = list(reversed(_load()))
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def add_history_entry(entry: Dict[str, Any]):
    try:
        history = _load()
        history.append(entry)
        write_json(HISTORY_FILE, history)
        return {"message": "Entry saved", "entry": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_history_entry(entry_id: str):
    try:
        history = _load()
        updated = [e for e in history if e.get("jd_id") != entry_id]
        write_json(HISTORY_FILE, updated)
        return {"message": f"Entry {entry_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{entry_id}/suggestions")
async def save_suggestions(entry_id: str, suggestions: Dict[str, Any]):
    try:
        history = _load()
        for entry in history:
            if entry.get("jd_id") == entry_id:
                entry["suggestions"] = suggestions
                break
        write_json(HISTORY_FILE, history)
        return {"message": "Suggestions saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
