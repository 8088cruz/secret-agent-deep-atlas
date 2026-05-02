"""Mission log helpers for Secret Agents.

The mission log is the audit trail for user messages, LLM responses, tool
calls, tool results, final responses, and ratings.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[1]
MISSION_LOG_FILE = BASE_DIR / "mission_log.json"

DEFAULT_MISSION_LOG: Dict[str, Any] = {"conversation": []}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_mission_log(log: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(log, dict):
        return {"conversation": []}

    conversation = log.get("conversation")
    if not isinstance(conversation, list):
        conversation = []

    normalized = dict(log)
    normalized["conversation"] = conversation
    return normalized


def load_mission_log() -> Dict[str, Any]:
    try:
        with MISSION_LOG_FILE.open("r", encoding="utf-8") as file:
            return normalize_mission_log(json.load(file))
    except FileNotFoundError:
        return dict(DEFAULT_MISSION_LOG)
    except json.JSONDecodeError:
        return dict(DEFAULT_MISSION_LOG)


def save_mission_log(log: Dict[str, Any]) -> None:
    MISSION_LOG_FILE.write_text(
        json.dumps(normalize_mission_log(log), indent=4),
        encoding="utf-8",
    )


def append_log_entry(log: Dict[str, Any], role: str, **fields: Any) -> Dict[str, Any]:
    """Append one timestamped audit event and return the log."""
    normalized = normalize_mission_log(log)
    entry = {
        "timestamp": utc_timestamp(),
        "role": role,
    }
    entry.update(fields)
    normalized["conversation"].append(entry)
    return normalized
