"""LLM interface for Secret Agents Phase 2.

This module owns prompt construction, the Ollama call, JSON extraction, and
response normalization. It returns dictionaries to the Flask app; it never
executes tools or writes state directly.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

try:  # Keep imports safe so smoke tests can run before dependencies are installed.
    import ollama  # type: ignore
except ImportError:  # pragma: no cover - depends on local environment
    ollama = None  # type: ignore

MODEL_NAME = os.environ.get("OLLAMA_MODEL", "llama3.1")
ALLOWED_RESPONSE_TYPES = {"final", "tool_call"}
ALLOWED_TOOLS = {"weather", "decryptor"}
ALLOWED_STATE_UPDATE_KEYS = {
    "mission_phase",
    "active",
    "completed",
    "destination",
    "city",
    "weather_summary",
    "disguise",
    "decoded_message",
}

SYSTEM_PROMPT = """
You are Mission Control for Secret Agents, a web-based spy mission game.

You are not a general chatbot. You are an agentic game controller inside a
bounded Python execution loop.

Current mission state is authoritative. Python owns validation, tool execution,
state persistence, and audit logging. You may request tools or propose small
state updates, but you never execute tools and never write files.

Your job:
- Guide the player through one fixed spy mission.
- Decide whether a tool is needed.
- Request tools only through the allowed JSON protocol.
- Use current mission state to keep continuity.
- Keep the player on mission.
- Return only valid JSON. No Markdown. No commentary outside JSON. No code fences.

Allowed tools:
1. weather
   Purpose: Get weather for a city.
   Required parameters:
   - city: string

2. decryptor
   Purpose: Decode a Caesar cipher message.
   Required parameters:
   - ciphertext: string
   - shift: integer

Never invent unsupported tool names.

If a tool is needed, return exactly this shape:
{
  "type": "tool_call",
  "tool": "weather",
  "parameters": {
    "city": "Paris"
  },
  "reason": "The player needs weather data before choosing a disguise."
}

If no tool is needed, return exactly this shape:
{
  "type": "final",
  "message": "Player-facing mission response here."
}

If mission state should change, include state_update in a final response:
{
  "type": "final",
  "message": "Mission phase updated.",
  "state_update": {
    "mission_phase": "weather_checked"
  }
}

Supported mission phases:
- briefing
- destination_selected
- weather_checked
- disguise_selected
- cipher_challenge
- decoded
- complete

Mission behavior:
- In briefing, introduce the objective and tell the player to ask for the destination.
- In destination_selected, encourage the player to check weather.
- In weather_checked, recommend or confirm a disguise.
- In cipher_challenge, help decode the Caesar cipher.
- In decoded, tell the player to report mission completion.
- In complete, congratulate the player and stop advancing the mission.

Important tool-result rule:
If TOOL_RESULT is provided, use it to produce a final player-facing response.
Do not request the same tool again unless the tool failed and the missing
parameter is clear.

Guardrails:
- Keep responses concise and in spy-game style.
- If the player goes off mission, redirect them back to the current objective.
- If a required tool parameter is missing, ask the player for the missing information.
- Return valid JSON only.
""".strip()


def extract_json(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from model output.

    Some local models wrap JSON in Markdown fences or add accidental prefix/suffix
    text. This function scans for the first decodable JSON object and returns it.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty LLM response")

    cleaned = text.strip()

    # Remove common Markdown fence wrappers without depending on exact formatting.
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON response must be an object")
        return parsed

    raise ValueError("No JSON object found in LLM response")


def _sanitize_state_update(state_update: Any) -> Dict[str, Any] | None:
    if not isinstance(state_update, dict):
        return None
    sanitized = {
        key: value
        for key, value in state_update.items()
        if key in ALLOWED_STATE_UPDATE_KEYS
    }
    return sanitized or None


def normalize_llm_response(response: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize an LLM response into the Secret Agents JSON protocol."""
    if not isinstance(response, dict):
        return {
            "type": "final",
            "message": "Mission control returned an invalid response. Try a simpler command.",
        }

    response_type = response.get("type")
    if response_type not in ALLOWED_RESPONSE_TYPES:
        return {
            "type": "final",
            "message": "Mission control returned an unsupported response type. Try a simpler command.",
            "error": f"Unsupported response type: {response_type}",
        }

    if response_type == "final":
        message = response.get("message")
        if not isinstance(message, str) or not message.strip():
            message = "Mission control has no further instructions yet."
        normalized: Dict[str, Any] = {
            "type": "final",
            "message": message.strip(),
        }
        state_update = _sanitize_state_update(response.get("state_update"))
        if state_update:
            normalized["state_update"] = state_update
        return normalized

    # response_type == "tool_call"
    tool = response.get("tool")
    parameters = response.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    if tool not in ALLOWED_TOOLS:
        return {
            "type": "final",
            "message": f"Mission control requested unsupported tool '{tool}'. Stay on mission and try again.",
            "error": f"Unsupported tool: {tool}",
        }

    return {
        "type": "tool_call",
        "tool": tool,
        "parameters": parameters,
        "reason": response.get("reason", "Tool requested by Mission Control."),
    }


def build_prompt(
    user_message: str,
    context: Dict[str, Any] | None = None,
    tool_result: Dict[str, Any] | None = None,
) -> str:
    """Build the full prompt sent to the local LLM."""
    context = context or {}

    tool_result_instruction = ""
    if tool_result is not None:
        tool_result_instruction = (
            "\nIMPORTANT: TOOL_RESULT is already available. Use it to produce a "
            "final JSON response. Do not request the same tool again unless the "
            "tool result is unusable.\n"
        )

    return f"""
{SYSTEM_PROMPT}
{tool_result_instruction}
CURRENT_MISSION_STATE:
{json.dumps(context, indent=2)}

TOOL_RESULT:
{json.dumps(tool_result, indent=2) if tool_result is not None else "null"}

PLAYER_MESSAGE:
{user_message}

Return only valid JSON.
""".strip()


def _ollama_generate(full_prompt: str) -> str:
    """Call Ollama and return raw text.

    Newer Ollama clients support `format="json"`; if the installed client does
    not, fall back to a normal generate call.
    """
    if ollama is None:
        raise RuntimeError("The ollama Python package is not installed.")

    client = ollama.Client()
    generate_kwargs = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "options": {"temperature": 0.2},
    }

    try:
        response = client.generate(**generate_kwargs, format="json")
    except TypeError:  # Older ollama package.
        response = client.generate(**generate_kwargs)

    return str(response.get("response", ""))


def send_to_llm(
    user_message: str,
    context: Dict[str, Any] | None = None,
    tool_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Send a message/context to the LLM and return a normalized protocol dict."""
    full_prompt = build_prompt(
        user_message=user_message,
        context=context,
        tool_result=tool_result,
    )

    try:
        raw_text = _ollama_generate(full_prompt)
        parsed = extract_json(raw_text)
        return normalize_llm_response(parsed)
    except Exception as exc:  # Keep the app up when Ollama is down or output is malformed.
        print(f"Error communicating with or parsing LLM response: {exc}")
        return {
            "type": "final",
            "message": (
                "Mission control had trouble reaching the local LLM. "
                "Using deterministic mission fallback when possible."
            ),
            "error": str(exc),
        }
