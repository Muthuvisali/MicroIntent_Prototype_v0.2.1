"""Browser entry point for the static demo (runs inside Pyodide).

Mirrors the FastAPI routes in app/main.py so the unchanged UI can call
/chat, /compare and /health without a server.
"""
import json
import os

os.environ["MICROINTENT_DEMO"] = "1"
os.environ["MICROINTENT_MODE"] = "deterministic"

from pydantic import ValidationError

from app.models import ChatRequest
from app.services.comparison import compare_strategies
from app.services.pipeline import run_pipeline

VERSION = "0.3.1"


def handle(path: str, body: str) -> str:
    """Return a JSON envelope: {"status": <http status>, "body": <response JSON string>}."""
    try:
        if path == "/health":
            out = json.dumps({"ok": True, "version": VERSION, "demo": True, "runtime": "pyodide"})
        elif path == "/chat":
            out = run_pipeline(ChatRequest.model_validate_json(body)).model_dump_json()
        elif path == "/compare":
            out = compare_strategies(ChatRequest.model_validate_json(body)).model_dump_json()
        else:
            return json.dumps({"status": 404, "body": json.dumps({"detail": "Not Found"})})
        return json.dumps({"status": 200, "body": out})
    except ValidationError as exc:
        return json.dumps({"status": 422, "body": json.dumps({"detail": exc.errors(include_url=False)}, default=str)})
