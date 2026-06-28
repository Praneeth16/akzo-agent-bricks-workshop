"""FastAPI app for the Finance controlling copilot.

Serves the JSON API under /api/* and the built React frontend (static) at /.
Run locally:  uvicorn main:app --reload --port 8000  (from backend/, with the CLI profile env set)
In Databricks Apps: app.yaml runs uvicorn on $DATABRICKS_APP_PORT.
"""
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import databricks_client as dbx
from actions_api import build_actions_router

app = FastAPI(title="AkzoNobel Finance Controlling Copilot")

# Action Plane routes — /api/act, /api/actions, approve, execute.
app.include_router(build_actions_router("finance-copilot"))

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


class VarianceReq(BaseModel):
    product_line: str
    region: str
    from_period: str
    to_period: str


class SaveReq(BaseModel):
    kind: str  # "variance" | "ask"
    title: str
    summary: str
    payload: dict[str, Any]
    product_line: Optional[str] = None
    region: Optional[str] = None
    from_period: Optional[str] = None
    to_period: Optional[str] = None
    question: Optional[str] = None


# ---- API routes -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user()}


@app.post("/api/ask")
def ask(req: AskReq):
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    try:
        return agent.ask(req.question)
    except Exception as e:
        raise HTTPException(500, f"ask failed: {e}")


@app.post("/api/variance")
def variance(req: VarianceReq):
    try:
        return agent.variance(
            req.product_line, req.region, req.from_period, req.to_period
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"variance failed: {e}")


@app.post("/api/save")
def save(req: SaveReq):
    try:
        return agent.save_analysis(
            kind=req.kind, title=req.title, summary=req.summary, payload=req.payload,
            product_line=req.product_line, region=req.region,
            from_period=req.from_period, to_period=req.to_period, question=req.question,
        )
    except Exception as e:
        raise HTTPException(500, f"save failed: {e}")


@app.get("/api/saved")
def saved():
    try:
        return {"analyses": agent.list_saved()}
    except Exception as e:
        raise HTTPException(500, f"list saved failed: {e}")


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
        # SPA fallback: any non-API path serves index.html.
        candidate = os.path.join(_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
