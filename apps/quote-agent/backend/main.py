"""FastAPI app for the Pricing / Quote agent.

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

app = FastAPI(title="AkzoNobel Pricing & Quote Agent")

# Action Plane routes — /api/act, /api/actions, approve, execute.
app.include_router(build_actions_router("quote-agent"))

# CORS so the Vite dev server (5173) can call the API during local frontend dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- request models -------------------------------------------------------
class ParseReq(BaseModel):
    rfq_text: str


class PriceReq(BaseModel):
    sku: str
    region: Optional[str] = None


class QuoteReq(BaseModel):
    account_id: str
    sku: str
    region: Optional[str] = None
    quantity_units: int
    list_price_eur: float
    standard_cost_eur: float
    discount_pct: float = 0.0
    rationale: Optional[str] = None


class DecisionReq(BaseModel):
    decision: str  # "approved" | "rejected"
    approver: str
    comment: Optional[str] = None


# ---- API routes -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user()}


@app.post("/api/parse")
def parse(req: ParseReq):
    if not req.rfq_text.strip():
        raise HTTPException(400, "rfq_text is required")
    try:
        return agent.parse_rfq(req.rfq_text)
    except Exception as e:
        raise HTTPException(500, f"parse failed: {e}")


@app.post("/api/price")
def price(req: PriceReq):
    try:
        return agent.price(req.sku, req.region)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"price failed: {e}")


@app.post("/api/quote")
def quote(req: QuoteReq):
    try:
        draft = agent.draft_quote(
            req.list_price_eur, req.standard_cost_eur, req.quantity_units, req.discount_pct
        )
        rationale = req.rationale or (
            f"{req.quantity_units} units of {req.sku} at {req.discount_pct}% discount; "
            f"net {draft['net_unit_price_eur']} EUR/unit, margin {draft['margin_pct']}%."
        )
        if draft["guardrail_flags"]:
            rationale += " GUARDRAIL: " + " ".join(draft["guardrail_flags"])
        written = agent.create_quote(
            account_id=req.account_id, sku=req.sku, region=req.region or "",
            quantity_units=req.quantity_units, list_price_eur=req.list_price_eur,
            quoted_price_eur=draft["net_unit_price_eur"], discount_pct=req.discount_pct,
            rationale=rationale,
        )
        return {"draft": draft, **written}
    except Exception as e:
        raise HTTPException(500, f"quote failed: {e}")


@app.get("/api/approvals")
def approvals(status: str = "pending"):
    try:
        return {"quotes": agent.list_approvals(status)}
    except Exception as e:
        raise HTTPException(500, f"approvals failed: {e}")


@app.post("/api/approvals/{quote_id}")
def decide(quote_id: int, req: DecisionReq):
    try:
        return agent.decide(quote_id, req.decision, req.approver, req.comment)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"decision failed: {e}")


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
