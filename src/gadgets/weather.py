"""Weather gadget for Secret Agents.

Phase 1 intentionally uses a fake/static weather response. This keeps the
agent loop testable without API keys or network dependencies.
"""

from __future__ import annotations


def get_weather(location: str) -> str:
    """Return a deterministic weather summary for the requested city."""
    clean_location = str(location).strip()
    weather = "Sunny"
    temperature = 25
    return f"Weather in {clean_location}: {weather}, {temperature}°C"
