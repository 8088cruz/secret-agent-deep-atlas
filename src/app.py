"""Flask/Socket.IO entrypoint for Secret Agents Phase 2."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from llm.llm_interface import normalize_llm_response, send_to_llm
from utils.game_state import apply_state_update, load_game_state, save_game_state
from utils.mission_flow import (
    compose_tool_final_response,
    detect_direct_tool_request,
    handle_deterministic_mission_command,
    is_useful_tool_final_response,
    phase_redirect_response,
    state_update_for_tool_result,
)
from utils.mission_log import append_log_entry, load_mission_log, save_mission_log
from utils.tool_executor import execute_tool

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_AGENTS_SECRET_KEY", "dev-secret-agents")

# Threading mode keeps the starter project easy to run without eventlet/gevent.
socketio = SocketIO(app, async_mode="threading")


@app.route("/")
def index():
    return render_template("index.html")


def _finalize_response(response: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the browser receives a final player-facing message."""
    normalized = normalize_llm_response(response)
    if normalized.get("type") == "final" and normalized.get("message"):
        return normalized
    return phase_redirect_response(state)


def _save_and_emit(state: Dict[str, Any], log: Dict[str, Any], final_response: Dict[str, Any]) -> None:
    """Persist state/log and send one final response to the browser."""
    state_update = final_response.get("state_update")
    if isinstance(state_update, dict):
        state = apply_state_update(state, state_update)
        log = append_log_entry(log, "state", state_update=state_update)

    log = append_log_entry(log, "final", response=final_response)
    save_game_state(state)
    save_mission_log(log)
    emit("response", {"message": final_response.get("message", "")})


@socketio.on("message")
def handle_message(message):
    """Handle one player message through the Phase 2 mission loop."""
    user_message = str(message or "").strip()
    if not user_message:
        emit("response", {"message": "Mission control did not receive a command."})
        return

    state = load_game_state()
    log = load_mission_log()
    log = append_log_entry(log, "user", message=user_message)

    # Phase 2 deterministic commands make the demo stable without waiting on a
    # local model for obvious mission-state transitions.
    deterministic = handle_deterministic_mission_command(user_message, state)
    if deterministic:
        if isinstance(deterministic.get("state"), dict):
            state = deterministic["state"]

        state_update = deterministic.get("state_update")
        if isinstance(state_update, dict):
            state = apply_state_update(state, state_update)

        final_response = deterministic["response"]
        log = append_log_entry(
            log,
            "deterministic",
            kind=deterministic.get("kind"),
            response=final_response,
        )
        _save_and_emit(state, log, final_response)
        return

    first_response = normalize_llm_response(send_to_llm(user_message, context=state))
    log = append_log_entry(log, "llm", response=first_response)

    if first_response.get("type") == "tool_call":
        direct_tool_request = {
            "tool": first_response.get("tool"),
            "parameters": first_response.get("parameters", {}),
            "reason": first_response.get("reason", "LLM requested tool."),
        }
    else:
        direct_tool_request = detect_direct_tool_request(user_message, state)

    if direct_tool_request:
        tool_name = direct_tool_request["tool"]
        parameters = direct_tool_request.get("parameters", {})
        tool_result = execute_tool(tool_name, parameters)

        log = append_log_entry(
            log,
            "tool",
            tool=tool_name,
            parameters=parameters,
            result=tool_result,
            reason=direct_tool_request.get("reason"),
        )

        tool_state_update = state_update_for_tool_result(tool_result, state)
        state_for_finalization = (
            apply_state_update(state, tool_state_update) if tool_state_update else state
        )

        llm_final = normalize_llm_response(
            send_to_llm(user_message, context=state_for_finalization, tool_result=tool_result)
        )
        log = append_log_entry(log, "llm_final", response=llm_final)

        if is_useful_tool_final_response(llm_final, tool_result):
            # Keep Python's deterministic state transition as the source of truth.
            final_response = dict(llm_final)
            if tool_state_update:
                final_response["state_update"] = {
                    **final_response.get("state_update", {}),
                    **tool_state_update,
                }
        else:
            final_response = compose_tool_final_response(tool_result, state)
            log = append_log_entry(log, "fallback", reason="deterministic_tool_final", response=final_response)
    else:
        final_response = _finalize_response(first_response, state)

    _save_and_emit(state, log, final_response)


@socketio.on("rate_interaction")
def handle_rating(data):
    """Persist simple UI ratings emitted by the starter frontend."""
    log = load_mission_log()
    log = append_log_entry(log, "rating", rating=data)
    save_mission_log(log)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)
