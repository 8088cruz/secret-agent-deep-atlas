"""Plain-Python smoke tests for Secret Agents Phase 1.

Run from the project root with:
    python tests/smoke_phase1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from llm.llm_interface import extract_json  # noqa: E402
from utils.game_state import load_game_state, save_game_state  # noqa: E402
from utils.mission_log import load_mission_log, save_mission_log  # noqa: E402
from utils.tool_executor import execute_tool  # noqa: E402


def main() -> None:
    weather = execute_tool("weather", {"city": "Paris"})
    assert weather["ok"] is True
    assert "Weather in Paris" in weather["result"]

    decoded = execute_tool("decryptor", {"ciphertext": "KHOOR", "shift": 3})
    assert decoded["ok"] is True
    assert "HELLO" in decoded["result"]

    assert execute_tool("weather", {})["ok"] is False
    assert execute_tool("decryptor", {"ciphertext": "KHOOR"})["ok"] is False
    assert execute_tool("not_a_tool", {})["ok"] is False

    parsed = extract_json('```json\n{"type":"final","message":"ready"}\n```')
    assert parsed == {"type": "final", "message": "ready"}

    state = load_game_state()
    save_game_state(state)

    log = load_mission_log()
    save_mission_log(log)

    print("Phase 1 smoke tests passed.")


if __name__ == "__main__":
    main()
