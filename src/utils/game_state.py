"""JSON-backed game state helpers for Secret Agents Phase 2.

Python owns mission-state persistence. The LLM may propose a `state_update`,
but writes are bounded to known current-mission fields and saved as readable
JSON under `src/game_state.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[1]
GAME_STATE_FILE = BASE_DIR / "game_state.json"

MISSION_ID = "mission-001"
MISSION_CITY = "Paris"
MISSION_DESTINATION = "France"
MISSION_CIPHERTEXT = "JVUNYHABSHAPVUZ HNLUA"
MISSION_CIPHER_SHIFT = 7
MISSION_OBJECTIVE = "Recover the package and report back to mission control."

ALLOWED_MISSION_FIELDS = {
    "mission_id",
    "active",
    "completed",
    "mission_phase",
    "destination",
    "city",
    "weather_summary",
    "disguise",
    "ciphertext",
    "cipher_shift",
    "decoded_message",
    "objective",
}

VALID_PHASES = {
    "briefing",
    "destination_selected",
    "weather_checked",
    "disguise_selected",
    "cipher_challenge",
    "decoded",
    "complete",
}


def default_current_mission() -> Dict[str, Any]:
    """Return the fixed, project-sized demo mission."""
    return {
        "mission_id": MISSION_ID,
        "active": True,
        "completed": False,
        "mission_phase": "briefing",
        "destination": MISSION_DESTINATION,
        "city": MISSION_CITY,
        "weather_summary": None,
        "disguise": None,
        "ciphertext": MISSION_CIPHERTEXT,
        "cipher_shift": MISSION_CIPHER_SHIFT,
        "decoded_message": None,
        "objective": MISSION_OBJECTIVE,
    }


def new_mission() -> Dict[str, Any]:
    """Create a fresh fixed mission state."""
    return {"current_mission": default_current_mission()}


DEFAULT_GAME_STATE: Dict[str, Any] = new_mission()


def _json_copy(value: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe deep copy."""
    return json.loads(json.dumps(value))


def normalize_mission(mission: Dict[str, Any] | None) -> Dict[str, Any]:
    """Ensure a mission has the full Phase 2 schema."""
    normalized = default_current_mission()

    if isinstance(mission, dict):
        for key, value in mission.items():
            if key in ALLOWED_MISSION_FIELDS:
                normalized[key] = value

    phase = normalized.get("mission_phase")
    if phase not in VALID_PHASES:
        normalized["mission_phase"] = "briefing"

    try:
        normalized["cipher_shift"] = int(normalized.get("cipher_shift", MISSION_CIPHER_SHIFT))
    except (TypeError, ValueError):
        normalized["cipher_shift"] = MISSION_CIPHER_SHIFT

    normalized["active"] = bool(normalized.get("active", True))
    normalized["completed"] = bool(normalized.get("completed", False))

    return normalized


def normalize_game_state(state: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize loaded state into the required Phase 2 shape."""
    if not isinstance(state, dict):
        return new_mission()

    return {
        "current_mission": normalize_mission(state.get("current_mission")),
    }


def load_game_state() -> Dict[str, Any]:
    """Load game state from JSON, returning a fresh mission on failure."""
    try:
        with GAME_STATE_FILE.open("r", encoding="utf-8") as file:
            return normalize_game_state(json.load(file))
    except FileNotFoundError:
        return new_mission()
    except json.JSONDecodeError:
        return new_mission()


def save_game_state(state: Dict[str, Any]) -> None:
    """Persist game state as pretty JSON."""
    GAME_STATE_FILE.write_text(
        json.dumps(normalize_game_state(state), indent=4),
        encoding="utf-8",
    )


def apply_state_update(state: Dict[str, Any], state_update: Dict[str, Any] | None) -> Dict[str, Any]:
    """Safely merge a bounded update into `current_mission`."""
    normalized = normalize_game_state(state)

    if isinstance(state_update, dict):
        current = normalized["current_mission"]
        for key, value in state_update.items():
            if key not in ALLOWED_MISSION_FIELDS:
                continue
            if key == "mission_phase" and value not in VALID_PHASES:
                continue
            if key == "cipher_shift":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            current[key] = value

    return normalize_game_state(normalized)


def update_current_mission(state: Dict[str, Any], state_update: Dict[str, Any] | None) -> Dict[str, Any]:
    """Alias used by the Phase 2 execution plan."""
    return apply_state_update(state, state_update)
