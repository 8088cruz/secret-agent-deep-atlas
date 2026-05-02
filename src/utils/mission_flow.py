"""Deterministic mission flow helpers for Secret Agents Phase 2.

The LLM is still allowed to plan and request tools, but these helpers keep the
single demo mission stable when a local model is weak, unavailable, or too
chatty. They contain no Flask dependencies so they can be smoke-tested directly.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from utils.game_state import new_mission

MISSION_PHASES = [
    "briefing",
    "destination_selected",
    "weather_checked",
    "disguise_selected",
    "cipher_challenge",
    "decoded",
    "complete",
]

START_COMMANDS = {
    "new mission",
    "start mission",
    "start new mission",
    "reset mission",
}

DEFAULT_DISGUISE = "sunglasses and a light jacket"


def current_mission(state: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return the current mission dictionary, or an empty dict."""
    if not isinstance(state, dict):
        return {}
    mission = state.get("current_mission")
    return mission if isinstance(mission, dict) else {}


def normalize_command(message: str) -> str:
    """Normalize a player message for simple deterministic matching."""
    text = str(message or "").strip().lower()
    text = re.sub(r"[.!?]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_start_mission_command(message: str) -> bool:
    return normalize_command(message) in START_COMMANDS


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def is_destination_request(message: str) -> bool:
    text = normalize_command(message)
    return text in {"destination", "my destination"} or _has_any(
        text,
        (
            "where am i going",
            "where do i go",
            "where should i go",
            "what is my destination",
            "what's my destination",
            "where is the mission",
        ),
    )


def is_completion_request(message: str) -> bool:
    text = normalize_command(message)
    return _has_any(
        text,
        (
            "mission complete",
            "complete mission",
            "package was recovered",
            "package recovered",
            "operation complete",
            "objective complete",
        ),
    )


def extract_disguise(message: str) -> Optional[str]:
    """Extract an obvious disguise choice from a player message."""
    raw = str(message or "").strip()
    text = normalize_command(raw)

    patterns = [
        r"(?:my disguise is|my disguise will be)\s+(.+)$",
        r"(?:i will pack|i'll pack|i am packing|i'm packing)\s+(.+)$",
        r"(?:i choose|i chose|i pick|i picked)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            disguise = match.group(1).strip(" .!?\"'")
            return disguise or None

    if _has_any(text, ("sunglasses", "light jacket", "jacket", "trench coat", "hat")):
        return raw.strip(" .!?") or DEFAULT_DISGUISE

    return None


def handle_deterministic_mission_command(
    message: str,
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Handle obvious non-tool mission commands before asking the LLM.

    Returns a dict with a final response and optional replacement state/update,
    or None when the LLM/tool loop should handle the message.
    """
    mission = current_mission(state)

    if is_start_mission_command(message):
        fresh_state = new_mission()
        fresh_mission = current_mission(fresh_state)
        return {
            "handled": True,
            "kind": "start_mission",
            "state": fresh_state,
            "response": {
                "type": "final",
                "message": (
                    "Operation Night Rose is live. Objective: "
                    f"{fresh_mission.get('objective')} Ask for your destination when ready."
                ),
            },
        }

    if mission.get("completed") is True and not is_start_mission_command(message):
        return {
            "handled": True,
            "kind": "mission_already_complete",
            "response": {
                "type": "final",
                "message": "This operation is already closed. Say 'Start new mission' to reset the board.",
            },
        }

    if is_destination_request(message):
        destination = mission.get("destination") or "France"
        city = mission.get("city") or "Paris"
        update = {"mission_phase": "destination_selected"}
        return {
            "handled": True,
            "kind": "destination_request",
            "state_update": update,
            "response": {
                "type": "final",
                "message": (
                    f"Your destination is {city}, {destination}. "
                    "Next step: check the weather before choosing your disguise."
                ),
                "state_update": update,
            },
        }

    # Do not treat tool-intent commands as disguise selections just because
    # they contain the word "disguise". Let the tool loop handle these next.
    normalized_text = normalize_command(message)
    if _has_any(normalized_text, ("weather", "forecast", "decode", "decrypt", "cipher", "intercepted message")):
        return None

    disguise = extract_disguise(message)
    if disguise:
        ciphertext = mission.get("ciphertext") or "JVUNYHABSHAPVUZ HNLUA"
        shift = mission.get("cipher_shift") or 7
        update = {
            "mission_phase": "cipher_challenge",
            "disguise": disguise,
        }
        return {
            "handled": True,
            "kind": "disguise_selected",
            "state_update": update,
            "response": {
                "type": "final",
                "message": (
                    f"Disguise logged: {disguise}. Intercepted message: {ciphertext}. "
                    f"It uses Caesar shift {shift}. Say 'Decode the intercepted message' when ready."
                ),
                "state_update": update,
            },
        }

    if is_completion_request(message):
        update = {
            "mission_phase": "complete",
            "completed": True,
            "active": False,
        }
        return {
            "handled": True,
            "kind": "mission_complete",
            "state_update": update,
            "response": {
                "type": "final",
                "message": "Mission complete. The package was recovered and Operation Night Rose is closed.",
                "state_update": update,
            },
        }

    return None


def _clean_city(city: str) -> str:
    city = city.strip(" ?.!,\n\t")
    # Avoid capturing trailing mission phrasing after the city.
    city = re.split(r"\b(?:before|so|and|please|agent)\b", city, maxsplit=1, flags=re.IGNORECASE)[0]
    return city.strip(" ?.!,\n\t")


def detect_direct_tool_request(
    message: str,
    state: Dict[str, Any] | None = None,
) -> Optional[Dict[str, Any]]:
    """Detect obvious weather/decryptor requests when the LLM misses them."""
    raw = str(message or "").strip()
    text = normalize_command(raw)
    mission = current_mission(state)

    weather_match = re.search(
        r"(?:weather\s+(?:in|for)\s+|what(?:'s| is)?\s+the\s+weather\s+(?:in|for)\s+|check\s+(?:the\s+)?weather\s+(?:in|for)\s+)([A-Za-z\s,]+)",
        raw,
        re.IGNORECASE,
    )
    if weather_match:
        city = _clean_city(weather_match.group(1))
        if city:
            return {
                "tool": "weather",
                "parameters": {"city": city},
                "reason": "Deterministic Phase 2 weather fallback with explicit city.",
            }

    if _has_any(text, ("weather", "forecast")):
        city = mission.get("city") or "Paris"
        return {
            "tool": "weather",
            "parameters": {"city": city},
            "reason": "Deterministic Phase 2 weather fallback using mission city.",
        }

    explicit_decode = re.search(
        r"(?:decode|decrypt)\s+(.+?)(?:\s+with\s+shift\s+|\s+shift\s+)(-?\d+)",
        raw,
        re.IGNORECASE,
    )
    if explicit_decode:
        ciphertext = explicit_decode.group(1).strip(" .!?\"'").upper()
        shift = int(explicit_decode.group(2))
        if ciphertext:
            return {
                "tool": "decryptor",
                "parameters": {
                    "ciphertext": ciphertext,
                    "shift": shift,
                },
                "reason": "Deterministic Phase 2 decryptor fallback with explicit ciphertext.",
            }

    if _has_any(text, ("decode", "decrypt", "cipher", "intercepted message")):
        ciphertext = mission.get("ciphertext") or "JVUNYHABSHAPVUZ HNLUA"
        shift = mission.get("cipher_shift", 7)
        return {
            "tool": "decryptor",
            "parameters": {
                "ciphertext": ciphertext,
                "shift": int(shift),
            },
            "reason": "Deterministic Phase 2 decryptor fallback using mission cipher.",
        }

    return None


def extract_decoded_message(tool_result: Dict[str, Any]) -> Optional[str]:
    result = tool_result.get("result")
    if not isinstance(result, str):
        return None
    prefix = "Unencrypted message:"
    if result.startswith(prefix):
        return result[len(prefix):].strip()
    return result.strip() or None


def state_update_for_tool_result(
    tool_result: Dict[str, Any],
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return deterministic mission-state changes for a successful tool call."""
    if not isinstance(tool_result, dict) or not tool_result.get("ok"):
        return {}

    tool = tool_result.get("tool")
    result = tool_result.get("result")

    if tool == "weather":
        return {
            "mission_phase": "weather_checked",
            "weather_summary": result,
        }

    if tool == "decryptor":
        decoded = extract_decoded_message(tool_result)
        update: Dict[str, Any] = {"mission_phase": "decoded"}
        if decoded:
            update["decoded_message"] = decoded
        return update

    return {}


def compose_tool_final_response(
    tool_result: Dict[str, Any],
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Compose a stable final response after a tool call."""
    if not isinstance(tool_result, dict) or not tool_result.get("ok"):
        return {
            "type": "final",
            "message": f"Mission tool failed: {tool_result.get('error', 'Unknown error') if isinstance(tool_result, dict) else 'Unknown error'}",
        }

    tool = tool_result.get("tool")
    result = tool_result.get("result")
    state_update = state_update_for_tool_result(tool_result, state)

    if tool == "weather":
        return {
            "type": "final",
            "message": (
                f"{result}. Recommended disguise: {DEFAULT_DISGUISE}. "
                "Confirm your disguise to receive the intercepted message."
            ),
            "state_update": state_update,
        }

    if tool == "decryptor":
        decoded = extract_decoded_message(tool_result) or str(result)
        return {
            "type": "final",
            "message": (
                f"Decoded message received: {decoded}. "
                "Recover the package, then report 'Mission complete.'"
            ),
            "state_update": state_update,
        }

    return {
        "type": "final",
        "message": str(result),
        "state_update": state_update,
    }


def is_useful_tool_final_response(
    response: Dict[str, Any],
    tool_result: Dict[str, Any],
) -> bool:
    """Heuristic guard for weak-model finalization after tool calls."""
    if not isinstance(response, dict) or response.get("type") != "final":
        return False
    message = str(response.get("message", "")).strip()
    if not message:
        return False

    lowered = message.lower()
    bad_phrases = (
        "could not finalize",
        "provide a city",
        "confirm the city",
        "need to know the weather",
        "try a simpler command",
        "trouble reaching",
    )
    if any(phrase in lowered for phrase in bad_phrases):
        return False

    tool = tool_result.get("tool")
    result = str(tool_result.get("result", ""))
    if tool == "weather":
        return any(token.lower() in lowered for token in ("sunny", "25", "weather", "disguise"))
    if tool == "decryptor":
        decoded = extract_decoded_message(tool_result) or result
        return decoded.lower() in lowered or "decoded" in lowered or "unencrypted" in lowered

    return True


def phase_redirect_response(state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a concise redirect based on the current mission phase."""
    mission = current_mission(state)
    phase = mission.get("mission_phase") or "briefing"

    if phase == "briefing":
        message = "Briefing is open. Ask 'Where am I going?' to receive your destination."
    elif phase == "destination_selected":
        message = "Destination is set. Ask to check the weather before choosing your disguise."
    elif phase == "weather_checked":
        message = "Weather is checked. Confirm your disguise, for example: 'I will pack sunglasses and a light jacket.'"
    elif phase in {"disguise_selected", "cipher_challenge"}:
        message = "Disguise is set. Decode the intercepted message to advance."
    elif phase == "decoded":
        message = "The message is decoded. Recover the package and report 'Mission complete.'"
    elif phase == "complete":
        message = "Operation is closed. Say 'Start new mission' to play again."
    else:
        message = "Stay on mission. Ask for the next objective."

    return {"type": "final", "message": message}
