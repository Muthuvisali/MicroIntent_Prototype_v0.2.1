from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app.models import ChatRequest, ChatResponse, StrategyComparison
from app.services.baseline import query_level_baseline
from app.services.pipeline import run_pipeline

app = FastAPI(title="MicroIntent Prototype", version="0.3.1")
STATIC = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "version": "0.3.1", "demo": os.getenv("MICROINTENT_DEMO") == "1"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return run_pipeline(req)


@app.post("/compare", response_model=StrategyComparison)
def compare(req: ChatRequest):
    result = run_pipeline(req)
    baseline = query_level_baseline(req)
    return StrategyComparison(
        query_level=baseline,
        micro_intent=result.placements,
        extracted_preferences=result.trace.explicit_session_context,
        note=(
            "The query-level baseline intentionally selects one broad-category sponsored result. "
            "MicroIntent can select up to the requested cap across independently scored answer components. "
            "This is a product experiment simulator, not a reproduction of Google's ad auction."
        ),
    )
