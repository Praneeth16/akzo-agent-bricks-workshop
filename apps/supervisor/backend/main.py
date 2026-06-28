"""FastAPI app for the Multi-domain Supervisor agent.

Serves the JSON API under /api/* and the built React frontend (static) at /.
Run locally:  uvicorn main:app --reload --port 8000  (from backend/, with the CLI profile env set)
In Databricks Apps: app.yaml runs uvicorn on $DATABRICKS_APP_PORT.
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import databricks_client as dbx
from actions_api import build_actions_router

app = FastAPI(title="AkzoNobel Multi-domain Supervisor Agent")

# Action Plane routes — /api/act, /api/actions, approve, execute.
app.include_router(build_actions_router("supervisor-agent"))

# CORS so the Vite dev server (5173) can call the API during local frontend dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- request models -------------------------------------------------------
class AskReq(BaseModel):
    question: str
    persona: Optional[str] = "controller"


class FeedbackReq(BaseModel):
    session_uuid: str
    rating: int  # +1 thumbs up, -1 thumbs down
    note: Optional[str] = None


# ---- API routes -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user(), "personas": list(agent.PERSONAS.keys())}


@app.post("/api/ask")
def ask(req: AskReq):
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    try:
        return agent.ask(req.question, req.persona or "controller")
    except Exception as e:
        raise HTTPException(500, f"ask failed: {e}")


@app.post("/api/feedback")
def feedback(req: FeedbackReq):
    if not req.session_uuid:
        raise HTTPException(400, "session_uuid is required")
    try:
        return agent.record_feedback(req.session_uuid, req.rating, req.note)
    except Exception as e:
        raise HTTPException(500, f"feedback failed: {e}")


# ---- static frontend (built React) ---------------------------------------
# Mounted last so /api/* wins. Serves frontend/dist if it exists.
_HERE = os.path.dirname(os.path.abspath(__file__))
_DIST = os.path.normpath(os.path.join(_HERE, "..", "frontend", "dist"))

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = os.path.join(_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
