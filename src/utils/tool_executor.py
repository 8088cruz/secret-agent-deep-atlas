"""Bounded tool dispatch for Secret Agents.

The LLM may request a tool, but Python validates the tool name and parameters
before executing anything. Phase 1 supports only weather and decryptor.
"""

from __future__ import annotations

from typing import Any, Dict

from gadgets.decryptor import decrypt_message
from gadgets.weather import get_weather

ALLOWED_TOOLS = {"weather", "decryptor"}


def execute_tool(tool_name: str, parameters: Dict[str, Any] | None) -> Dict[str, Any]:
    """Execute a supported tool and return a structured result dictionary."""
    parameters = parameters or {}

    if not isinstance(parameters, dict):
        return {
            "ok": False,
            "tool": tool_name,
            "error": "Tool parameters must be a JSON object.",
        }

    try:
        if tool_name == "weather":
            city = parameters.get("city") or parameters.get("location")
            if not city or not str(city).strip():
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": "Missing required parameter: city",
                }

            clean_city = str(city).strip()
            result = get_weather(clean_city)
            return {
                "ok": True,
                "tool": tool_name,
                "parameters": {"city": clean_city},
                "result": result,
            }

        if tool_name == "decryptor":
            ciphertext = parameters.get("ciphertext")
            shift = parameters.get("shift")

            if ciphertext is None or str(ciphertext) == "":
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": "Missing required parameter: ciphertext",
                }

            if shift is None:
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": "Missing required parameter: shift",
                }

            try:
                normalized_shift = int(shift)
            except (TypeError, ValueError):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": "Parameter shift must be an integer.",
                }

            result = decrypt_message(str(ciphertext), normalized_shift)
            return {
                "ok": True,
                "tool": tool_name,
                "parameters": {
                    "ciphertext": str(ciphertext),
                    "shift": normalized_shift,
                },
                "result": result,
            }

        return {
            "ok": False,
            "tool": tool_name,
            "error": f"Unknown tool requested: {tool_name}",
            "allowed_tools": sorted(ALLOWED_TOOLS),
        }

    except Exception as exc:  # Defensive boundary: tools must not crash the app.
        return {
            "ok": False,
            "tool": tool_name,
            "error": str(exc),
        }
