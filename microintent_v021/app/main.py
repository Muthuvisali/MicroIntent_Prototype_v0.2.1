from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app.models import ChatRequest, ChatResponse, StrategyComparison
from app.services.comparison import compare_strategies
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
    return compare_strategies(req)
