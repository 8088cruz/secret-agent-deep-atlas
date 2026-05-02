# Secret Agents — Phase 2 Notes

This package implements **Phase 2 — The Taskmaster** on top of the patched Phase 1 codebase.

## What changed

- `src/app.py`
  - Added Phase 2 mission loop handling.
  - Added deterministic command handling before the LLM for obvious mission transitions.
  - Kept the LLM JSON protocol and tool-call loop.
  - Added deterministic tool finalization guard so weak local LLM responses do not break the demo.

- `src/utils/game_state.py`
  - Added fixed `new_mission()` schema.
  - Added full Phase 2 mission state normalization.
  - Added safe bounded state-update merging.
  - Kept stable paths under `src/`.

- `src/utils/mission_flow.py`
  - Added deterministic mission helpers for:
    - start/reset mission
    - destination request
    - weather fallback using mission city
    - disguise selection
    - cipher decoding fallback using mission ciphertext/shift
    - mission completion
    - phase-aware redirect responses

- `src/llm/llm_interface.py`
  - Updated the system prompt for Phase 2.
  - Preserved strict JSON parsing and fallback behavior.
  - Added state-update key sanitization.
  - Rejects unsupported tool names before execution.

- `tests/smoke_phase2.py`
  - Added a no-Flask/no-Ollama smoke test for the Phase 2 mission flow.

- `src/game_state.json`
  - Reset to a fresh fixed mission.

- `src/mission_log.json`
  - Reset to an empty audit log.

## Run locally

```bash
cd secret_agents/src
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional, for LLM-backed responses:
ollama serve
ollama pull llama3.1

python app.py
```

Open:

```text
http://localhost:8080
```

## Final demo script

Use this exact browser sequence:

```text
Start new mission
Where am I going?
Check the weather there.
I will pack sunglasses and a light jacket.
Decode the intercepted message.
Mission complete. The package was recovered.
```

Expected final state in `src/game_state.json`:

```json
{
  "mission_phase": "complete",
  "completed": true,
  "active": false
}
```

## Smoke tests

From the project root:

```bash
python tests/smoke_phase1.py
python tests/smoke_phase2.py
```

From `src/`:

```bash
python -m compileall .
python -m json.tool game_state.json
python -m json.tool mission_log.json
```

## Notes

- The demo no longer depends on the local LLM perfectly following the tool protocol.
- Python remains the source of truth for validation, tool execution, persistence, and deterministic state transitions.
- Weather remains fake/static by design to avoid API keys and scope creep.
- The UI was not redesigned.
