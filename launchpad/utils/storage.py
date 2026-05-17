import os
import json
from datetime import datetime

# -------------------------
# Paths
# -------------------------

DATA_DIR = "data"
GOALS_FILE = os.path.join(DATA_DIR, "goals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


# -------------------------
# Helpers
# -------------------------

def ensure_data_dir():
    """
    Creates data directory if missing.
    """
    os.makedirs(DATA_DIR, exist_ok=True)


def read_json(file_path, default=None):
    """
    Safely read JSON file.
    """
    ensure_data_dir()

    if not os.path.exists(file_path):
        return default if default is not None else []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default if default is not None else []


def write_json(file_path, data):
    """
    Safely write JSON file.
    """
    ensure_data_dir()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -------------------------
# Goals Persistence
# -------------------------

def save_goals(goals):
    """
    Save goals locally.
    """
    write_json(GOALS_FILE, goals)


def load_goals():
    """
    Load goals from local storage.
    """
    return read_json(GOALS_FILE, default=[])


# -------------------------
# History Persistence
# -------------------------

def save_history(entry):
    """
    Save one history record locally.
    """

    history = load_history()

    entry["saved_at"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    history.append(entry)

    write_json(HISTORY_FILE, history)


def load_history():
    """
    Load history from local storage.
    """
    return read_json(HISTORY_FILE, default=[])


def clear_history():
    """
    Clear saved history.
    """
    write_json(HISTORY_FILE, [])