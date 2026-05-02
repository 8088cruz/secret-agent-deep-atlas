"""Phase 2 smoke tests for Secret Agents.

These tests avoid Flask and Ollama so they can run in a minimal environment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from utils.game_state import (  # noqa: E402
    apply_state_update,
    load_game_state,
    new_mission,
    save_game_state,
)
from utils.mission_flow import (  # noqa: E402
    compose_tool_final_response,
    detect_direct_tool_request,
    handle_deterministic_mission_command,
    state_update_for_tool_result,
)
from utils.mission_log import load_mission_log, save_mission_log  # noqa: E402
from utils.tool_executor import execute_tool  # noqa: E402


def assert_phase(state, phase: str) -> None:
    assert state["current_mission"]["mission_phase"] == phase


def main() -> None:
    state = new_mission()
    mission = state["current_mission"]

    # Required Phase 2 schema.
    required_keys = {
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
    assert required_keys == set(mission.keys())
    assert mission["mission_id"] == "mission-001"
    assert mission["city"] == "Paris"
    assert mission["ciphertext"] == "JVUNYHABSHAPVUZ HNLUA"
    assert mission["cipher_shift"] == 7
    assert_phase(state, "briefing")

    # Deterministic destination handling.
    destination = handle_deterministic_mission_command("Where am I going?", state)
    assert destination is not None
    state = apply_state_update(state, destination["state_update"])
    assert_phase(state, "destination_selected")

    # Weather request should not be mistaken for disguise selection just because
    # it contains the word "disguise".
    assert handle_deterministic_mission_command(
        "Check the weather before I choose a disguise.",
        state,
    ) is None

    # Weather request can use the mission city when player says "there".
    weather_request = detect_direct_tool_request("Check the weather there.", state)
    assert weather_request is not None
    assert weather_request["tool"] == "weather"
    assert weather_request["parameters"]["city"] == "Paris"

    weather = execute_tool(weather_request["tool"], weather_request["parameters"])
    assert weather["ok"] is True
    weather_update = state_update_for_tool_result(weather, state)
    state = apply_state_update(state, weather_update)
    assert_phase(state, "weather_checked")
    assert "Weather in Paris" in state["current_mission"]["weather_summary"]
    weather_final = compose_tool_final_response(weather, state)
    assert "Recommended disguise" in weather_final["message"]

    # Disguise selection presents the cipher challenge.
    disguise = handle_deterministic_mission_command(
        "I will pack sunglasses and a light jacket.",
        state,
    )
    assert disguise is not None
    state = apply_state_update(state, disguise["state_update"])
    assert_phase(state, "cipher_challenge")
    assert "sunglasses" in state["current_mission"]["disguise"]

    # Decode can use mission ciphertext/shift without the player repeating them.
    decode_request = detect_direct_tool_request("Decode the intercepted message.", state)
    assert decode_request is not None
    assert decode_request["tool"] == "decryptor"
    decoded = execute_tool(decode_request["tool"], decode_request["parameters"])
    assert decoded["ok"] is True
    assert "CONGRATULATIONS AGENT" in decoded["result"]
    decode_update = state_update_for_tool_result(decoded, state)
    state = apply_state_update(state, decode_update)
    assert_phase(state, "decoded")
    assert state["current_mission"]["decoded_message"] == "CONGRATULATIONS AGENT"

    # Mission completion closes the operation.
    complete = handle_deterministic_mission_command(
        "Mission complete. The package was recovered.",
        state,
    )
    assert complete is not None
    state = apply_state_update(state, complete["state_update"])
    assert_phase(state, "complete")
    assert state["current_mission"]["completed"] is True
    assert state["current_mission"]["active"] is False

    # JSON persistence stays valid.
    save_game_state(state)
    loaded = load_game_state()
    assert loaded["current_mission"]["mission_phase"] == "complete"

    log = load_mission_log()
    save_mission_log(log)
    json.loads((SRC_DIR / "game_state.json").read_text(encoding="utf-8"))
    json.loads((SRC_DIR / "mission_log.json").read_text(encoding="utf-8"))

    print("Phase 2 smoke tests passed.")


if __name__ == "__main__":
    main()
