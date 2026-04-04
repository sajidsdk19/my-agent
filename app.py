#!/usr/bin/env python3
"""
Flask web server for Claw Agent.
Run:  python app.py
Then open: http://localhost:5000

Author  : Sajid Khan  –  CTO, TechScape
Website : https://sajidkhan.me
GitHub  : https://github.com/sajidsdk19
"""

import sys
import os
import json
import uuid
import queue
import threading
from pathlib import Path

from flask import Flask, render_template, request, Response, jsonify, session as flask_session

# ── Import agent.py from same directory ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
import agent as _agent_module
from agent import (
    Agent, OllamaBackend, GeminiBackend,
    OLLAMA_OK, GEMINI_OK, SYSTEM_PROMPT,
)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(24))

# In-memory state (single-user tool)
_agents: dict[str, Agent]        = {}   # flask session id → Agent
_streams: dict[str, queue.Queue] = {}   # stream id → Queue


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_make_backend(model: str | None):
    """Wraps make_backend so it raises RuntimeError instead of sys.exit()."""
    try:
        return _agent_module.make_backend(model)
    except SystemExit as e:
        raise RuntimeError(
            f"Backend init failed (code {e.code}). "
            "Is Ollama running? Is GEMINI_API_KEY set?"
        )


def _sid() -> str:
    if "sid" not in flask_session:
        flask_session["sid"] = str(uuid.uuid4())
    return flask_session["sid"]


def _get_agent() -> Agent | None:
    return _agents.get(_sid())


def _get_or_create_agent(model: str | None = None) -> Agent:
    sid = _sid()
    agent = _agents.get(sid)
    if agent is None:
        backend = _safe_make_backend(model)
        agent = Agent(backend=backend)
        _agents[sid] = agent
    return agent


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    _sid()  # ensure cookie set
    return render_template("index.html")


@app.route("/api/models")
def api_models():
    models = []
    if OLLAMA_OK and OllamaBackend.is_running():
        for m in OllamaBackend.list_models():
            models.append({"id": m, "name": m, "backend": "ollama", "free": True})
    has_key = bool(
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    if GEMINI_OK and has_key:
        models.append({
            "id":      "gemini",
            "name":    "Gemini 2.5 Flash (Cloud)",
            "backend": "gemini",
            "free":    False,
        })
    return jsonify({"models": models})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data      = request.get_json(force=True) or {}
    user_msg  = (data.get("message") or "").strip()
    model     = data.get("model") or None

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    sid = _sid()
    # If model changed, create fresh agent
    existing = _agents.get(sid)
    if existing and model:
        current_model = existing.backend.name.split("/")[-1].split(":")[0]
        req_model     = (model if model != "gemini" else "gemini")
        if req_model not in existing.backend.name:
            existing = None  # force recreate

    try:
        agent = existing or _get_or_create_agent(model)
        _agents[sid] = agent
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    stream_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    _streams[stream_id] = q

    def run():
        try:
            agent.run_turn_streaming(user_msg, q)
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})
        finally:
            q.put(None)  # sentinel → closes SSE stream

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"stream_id": stream_id})


@app.route("/api/stream/<stream_id>")
def api_stream(stream_id):
    q = _streams.get(stream_id)
    if q is None:
        return jsonify({"error": "Unknown stream"}), 404

    def generate():
        try:
            while True:
                event = q.get(timeout=120)
                if event is None:
                    yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except queue.Empty:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent timed out'})}\n\n"
        finally:
            _streams.pop(stream_id, None)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/session/clear", methods=["POST"])
def api_clear():
    agent = _get_agent()
    if agent:
        agent.messages   = [{"role": "system", "content": SYSTEM_PROMPT}]
        agent.turn_count = 0
    return jsonify({"ok": True})


@app.route("/api/session/save", methods=["POST"])
def api_save():
    agent = _get_agent()
    if agent:
        path = agent.save_session()
        return jsonify({"ok": True, "path": str(path)})
    return jsonify({"error": "No active session"}), 400


@app.route("/api/status")
def api_status():
    agent = _get_agent()
    if agent:
        return jsonify({
            "model":      agent.backend.name,
            "cost":       agent.backend.cost,
            "turns":      agent.turn_count,
            "messages":   len(agent.messages),
            "session_id": agent.session_id,
            "cwd":        str(_agent_module.CWD),
        })
    return jsonify({"model": None, "turns": 0, "messages": 0, "cwd": str(_agent_module.CWD)})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000,
                        help="Port to run Flask on (default 5000; Electron uses 5001)")
    args = parser.parse_args()

    print(f"\n  🦞  Claw Agent Web UI")
    print(f"  Open → http://localhost:{args.port}")
    print(f"  Author : Sajid Khan · CTO TechScape")
    print(f"  Web    : https://sajidkhan.me")
    print(f"  GitHub : https://github.com/sajidsdk19\n")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
