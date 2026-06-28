"""Mock external-systems app — the governed external target for the Action Plane.

A safe stand-in for the systems agents act on (email, Teams, CRM, ERP/PO,
SharePoint, ServiceNow). Every endpoint:
  - accepts a JSON payload,
  - allocates a human-readable ref id (EMAIL-0001, PO-0001, ...),
  - logs a row to Lakebase `akzo.external_system_log`,
  - returns {ref_id, status, echo}.

No real email/PO is ever sent — this is the demo's blast-radius-zero target.
Calls reach it through the governed UC HTTP connection `akzo_external_systems`
(or directly under the app service principal as the documented fallback); either
way every action lands an auditable receipt in Lakebase.

Run locally:  uvicorn main:app --reload --port 8000  (from backend/, CLI profile env set)
In Databricks Apps: app.yaml runs uvicorn on $DATABRICKS_APP_PORT.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import databricks_client as dbx
import lakebase as lb

app = FastAPI(title="AkzoNobel Mock External Systems")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- table bootstrap ------------------------------------------------------
_TABLE_READY = False


def _ensure_table() -> None:
    """Create akzo.external_system_log on first use (idempotent)."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    lb.execute(
        """
        CREATE TABLE IF NOT EXISTS akzo.external_system_log (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ts          timestamptz NOT NULL DEFAULT now(),
            system      text        NOT NULL,
            ref_id      text        NOT NULL,
            request     jsonb       NOT NULL,
            created_by  text        NOT NULL
        )
        """
    )
    _TABLE_READY = True


# ref-id prefixes per system
_PREFIX = {
    "email": "EMAIL",
    "teams": "TEAMS",
    "crm": "CRM",
    "erp_po": "PO",
    "sharepoint": "SP",
    "servicenow": "SNOW",
}


def _record(system: str, payload: dict) -> dict:
    """Log the action and return {ref_id, status, echo}.

    ref_id is the per-system prefix + the new row's identity (e.g. PO-0001).
    """
    _ensure_table()
    created_by = dbx.current_user()
    # Insert first to obtain the identity, then derive the human ref id from it
    # and stamp it back — one row, one ref, fully auditable.
    row = lb.execute(
        """
        INSERT INTO akzo.external_system_log (system, ref_id, request, created_by)
        VALUES (%s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (system, "PENDING", json.dumps(payload), created_by),
        returning=True,
    )
    seq = int(row["id"])
    ref_id = f"{_PREFIX[system]}-{seq:04d}"
    lb.execute(
        "UPDATE akzo.external_system_log SET ref_id = %s WHERE id = %s",
        (ref_id, seq),
    )
    return {"ref_id": ref_id, "status": "accepted", "echo": payload}


# ---- request models -------------------------------------------------------
class EmailReq(BaseModel):
    to: str
    subject: str
    body: str


class TeamsReq(BaseModel):
    channel: str
    message: str


class CrmTaskReq(BaseModel):
    account: str
    task: str
    due: Optional[str] = None


class ErpPoReq(BaseModel):
    supplier: str
    sku: str
    qty: int
    amount_eur: float


class SharepointReq(BaseModel):
    path: str
    title: str


class ServiceNowReq(BaseModel):
    summary: str
    priority: Optional[str] = "P3"


# ---- action routes --------------------------------------------------------
@app.post("/email")
def post_email(req: EmailReq):
    try:
        return _record("email", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"email failed: {e}")


@app.post("/teams")
def post_teams(req: TeamsReq):
    try:
        return _record("teams", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"teams failed: {e}")


@app.post("/crm/task")
def post_crm_task(req: CrmTaskReq):
    try:
        return _record("crm", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"crm task failed: {e}")


@app.post("/erp/po")
def post_erp_po(req: ErpPoReq):
    try:
        return _record("erp_po", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"erp po failed: {e}")


@app.post("/sharepoint/upload")
def post_sharepoint(req: SharepointReq):
    try:
        return _record("sharepoint", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"sharepoint upload failed: {e}")


@app.post("/servicenow/ticket")
def post_servicenow(req: ServiceNowReq):
    try:
        return _record("servicenow", req.model_dump())
    except Exception as e:
        raise HTTPException(500, f"servicenow ticket failed: {e}")


# ---- ops routes -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user()}


@app.get("/api/log")
def log(limit: int = 50, system: Optional[str] = None):
    """Recent external_system_log rows for the demo."""
    try:
        _ensure_table()
        if system:
            rows = lb.query(
                "SELECT id, ts, system, ref_id, request, created_by "
                "FROM akzo.external_system_log WHERE system = %s "
                "ORDER BY id DESC LIMIT %s",
                (system, limit),
            )
        else:
            rows = lb.query(
                "SELECT id, ts, system, ref_id, request, created_by "
                "FROM akzo.external_system_log ORDER BY id DESC LIMIT %s",
                (limit,),
            )
        return {"rows": rows, "row_count": len(rows)}
    except Exception as e:
        raise HTTPException(500, f"log read failed: {e}")


# ---- minimal HTML status page --------------------------------------------
_ENDPOINTS = [
    ("POST", "/email", "to, subject, body"),
    ("POST", "/teams", "channel, message"),
    ("POST", "/crm/task", "account, task, due"),
    ("POST", "/erp/po", "supplier, sku, qty, amount_eur"),
    ("POST", "/sharepoint/upload", "path, title"),
    ("POST", "/servicenow/ticket", "summary, priority"),
    ("GET", "/api/health", "liveness + identity"),
    ("GET", "/api/log", "recent external_system_log rows"),
]


@app.get("/", response_class=HTMLResponse)
def index():
    rows = "".join(
        f"<tr><td><code>{m}</code></td><td><code>{p}</code></td><td>{d}</td></tr>"
        for m, p, d in _ENDPOINTS
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>AkzoNobel Mock External Systems</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
         margin: 48px auto; padding: 0 20px; color: #1a1a2e; }}
  h1 {{ font-size: 22px; }} .tag {{ color: #6b7280; font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
  td, th {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; }}
  code {{ background: #f4f4f8; padding: 2px 6px; border-radius: 4px; }}
</style></head>
<body>
  <h1>AkzoNobel — Mock External Systems</h1>
  <p class="tag">Governed external target for the Action Plane. Every call logs a
  receipt to Lakebase <code>akzo.external_system_log</code>. No real systems are touched.</p>
  <table>
    <tr><th>Method</th><th>Path</th><th>Payload / purpose</th></tr>
    {rows}
  </table>
</body></html>"""
