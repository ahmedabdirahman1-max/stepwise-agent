"""FastAPI entrypoint.

Run:  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000
"""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ANTHROPIC_API_KEY, AGENT_MODEL, MAX_STEPS
from .agent import run_agent, SAMPLE_REQUESTS
from .tools import TOOLS

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="StepWise — governed planner/executor agent (demo)", version="1.0.0")


class AskRequest(BaseModel):
    request: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "planner": "llm" if ANTHROPIC_API_KEY else "rules",
        "model": AGENT_MODEL if ANTHROPIC_API_KEY else None,
        "tools": list(TOOLS.keys()),
        "max_steps": MAX_STEPS,
    }


@app.get("/api/samples")
def samples() -> dict:
    return {"samples": SAMPLE_REQUESTS}


@app.post("/api/run")
def run(req: AskRequest) -> JSONResponse:
    request = (req.request or "").strip()
    if not request:
        return JSONResponse({"error": "Empty request."}, status_code=400)
    return JSONResponse(run_agent(request))


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
