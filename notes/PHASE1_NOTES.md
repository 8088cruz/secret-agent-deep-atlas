# Secret Agents — Phase 1 Notes

This package implements **Phase 1 — The Quartermaster** from `EXECUTION.md`.

## Run

```bash
cd secret_agents/src
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# In another terminal, if using Ollama:
ollama serve
ollama pull llama3.1

python app.py
```

Open:

```text
http://localhost:8080
```

Try:

```text
What is the weather in Paris?
Decode KHOOR with shift 3.
```

## Smoke tests

From the project root:

```bash
python tests/smoke_phase1.py
```

From `src/`:

```bash
python -m json.tool game_state.json
python -m json.tool mission_log.json
python -m compileall .
```

## Scope

Implemented:

- Flask/Socket.IO message loop
- Strict JSON LLM protocol parser
- Ollama-backed LLM interface
- Safe fallback if Ollama is unavailable or malformed output is returned
- Bounded `weather` and `decryptor` tool execution
- Stable JSON file paths
- `game_state.json` and `mission_log.json` persistence
- Rating event logging from the starter UI

Not implemented yet:

- Full Phase 2 mission progression
- Real weather API
- Database persistence
- Authentication
