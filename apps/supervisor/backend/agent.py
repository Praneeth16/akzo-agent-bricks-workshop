"""The Multi-domain Supervisor agent — route -> call domain legs -> fuse one governed answer.

This is the supervisor-SPECIFIC layer. It composes the shared modules:
  - databricks_client.chat()  -> the LLM router (which domains) and the fuser (one answer)
  - text2sql.ask()            -> each chosen domain leg, pointed at that domain's genie/*_space.md
  - lakebase                  -> persist the turn (agent_sessions) + human feedback (agent_feedback)

It is a faithful, self-contained reproduction of an Agent Bricks Multi-Agent Supervisor:
the per-domain `ROUTING_DESCRIPTION` lines below ARE the per-subagent "description" field you
fill in when registering each Genie space with a native MAS (reference endpoint in this
workspace: `mas-f14da7dc-endpoint`). See README for the upgrade path.

Verified router/fuser logic from notebooks/04_supervisor_agent.py.
"""
from __future__ import annotations

import json
import os
import uuid

import databricks_client as dbx
import lakebase as lb
import text2sql

SERVICE_IDENTITY = "supervisor-agent@service"  # app/service write identity in the audit trail

# Bundled genie space instructions, resolved relative to this file so the app is self-contained
# (works standalone in Databricks Apps). The supervisor points each leg's text2sql at its file.
_HERE = os.path.dirname(os.path.abspath(__file__))
GENIE_PATHS = {
    "FINANCE": os.path.join(_HERE, "finance_space.md"),
    "SCM": os.path.join(_HERE, "scm_space.md"),
    "COMMERCIAL": os.path.join(_HERE, "commercial_space.md"),
}

# Real Genie space ids (created from code by genie/create_genie_spaces.py). When a domain's id is set,
# its leg calls the REAL Genie space via the Conversation API; when blank, it falls back to the
# instruction-driven text2sql over the bundled *_space.md. Set via app.yaml env.
SPACE_IDS = {
    "FINANCE": os.environ.get("FINANCE_SPACE_ID", "").strip(),
    "SCM": os.environ.get("SCM_SPACE_ID", "").strip(),
    "COMMERCIAL": os.environ.get("COMMERCIAL_SPACE_ID", "").strip(),
}


def _user_genie_client(user_token: str | None):
    """A WorkspaceClient bound to the END USER's forwarded token (OBO), so Genie reads run under the
    caller's identity / row filters. Falls back to the app service principal when no token is present
    (local dev / non-SSO callers)."""
    if not user_token:
        return dbx.client()
    from databricks.sdk import WorkspaceClient
    # auth_type='pat' forces token-only auth so the SP OAuth in the app env (DATABRICKS_CLIENT_ID/
    # SECRET) does not collide with the forwarded user token ("more than one authorization method").
    return WorkspaceClient(host=dbx.client().config.host, token=user_token, auth_type="pat")


def _genie_leg(space_id: str, question: str, w=None) -> dict:
    """Call a REAL Genie space via the Conversation API: Genie generates + runs the governed SQL
    under `w`'s identity (the end user under OBO when provided). Returns {sql, rows, columns, row_count}."""
    w = w or dbx.client()
    msg = w.genie.start_conversation_and_wait(space_id=space_id, content=question)
    sql, rows, cols = "", [], []
    for att in (msg.attachments or []):
        if getattr(att, "query", None) is None:
            continue
        sql = att.query.query or sql
        # Fetch the result per the doc's .../query-result/{attachment_id}. Prefer the by-attachment
        # method; fall back to the message-level one across SDK versions.
        att_id = getattr(att, "attachment_id", None)
        res = None
        for getter in (
            lambda: w.genie.get_message_attachment_query_result(
                space_id=space_id, conversation_id=msg.conversation_id, message_id=msg.id, attachment_id=att_id),
            lambda: w.genie.get_message_query_result_by_attachment(
                space_id=space_id, conversation_id=msg.conversation_id, message_id=msg.id, attachment_id=att_id),
            lambda: w.genie.get_message_query_result(
                space_id=space_id, conversation_id=msg.conversation_id, message_id=msg.id),
        ):
            try:
                res = getter()
                break
            except Exception:
                continue
        sr = getattr(res, "statement_response", None) if res is not None else None
        if sr and getattr(sr, "result", None) and sr.result.data_array:
            cols = [c.name for c in sr.manifest.schema.columns]
            rows = [dict(zip(cols, r)) for r in sr.result.data_array]
    return {"sql": sql, "rows": rows, "columns": cols, "row_count": len(rows)}

# >>> THE LAYER YOU TWEAK <<< — one line per registered subagent describing what that domain
# knows. In a native MAS this is each subagent's "description" field. Editing it re-routes.
ROUTING_DESCRIPTION = {
    "FINANCE": "Gross margin, price / realized price per unit, FX translation, COGS / raw-material / "
    "freight / energy cost, budget variance. Use for any 'why did margin/price/cost change' question.",
    "SCM": "OTIF (on-time-in-full), inventory, stockouts, days of supply, transport lanes, lead times, "
    "service levels, backorders. Use for supply, service, delivery, or fulfilment questions.",
    "COMMERCIAL": "Customer accounts, churn risk/score, NPS, complaints, sales/revenue by account, "
    "pipeline. Use for customer-risk, retention, or account-impact questions.",
}

# Persona -> the governed data scope the trace notes. OBO at the Genie-call layer (reads only):
# the same routing runs, but each leg's SQL executes under the caller's identity, so a UC row
# filter narrows what each persona actually sees. Documented, not enforced in local dev.
PERSONAS = {
    "controller": {
        "label": "Group Controller",
        "scope": "all regions (EMEA / Americas / APAC / China)",
    },
    "emea_planner": {
        "label": "EMEA Supply Planner",
        "scope": "EMEA only — UC row filter on margin_actuals / otif enforced under this identity",
    },
    "rep": {
        "label": "Account Rep",
        "scope": "own accounts only — commercial rows filtered to this rep's book under OBO",
    },
}


# ---------------------------------------------------------------------------
# ROUTER — one LLM call: given the question + the routing descriptions, decide
# which domain subagents to consult and why. Returns {domains, reason}.
# ---------------------------------------------------------------------------
def _build_router_prompt(question: str, descriptions: dict) -> str:
    lines = "\n".join(f"- {d}: {desc}" for d, desc in descriptions.items())
    return (
        "You are the routing controller for an AkzoNobel Multi-Agent Supervisor. "
        "Registered domain subagents:\n"
        f"{lines}\n\n"
        "Decide which subagent(s) are needed to fully answer the user's question. A cross-domain "
        "'why' question often needs several. For EACH chosen domain, also write a focused "
        "subquestion phrased ENTIRELY in that domain's own terms (e.g. ask SCM about OTIF / lead "
        "times / stockouts / service level — never about 'margin'; ask Commercial about churn / "
        "at-risk accounts; ask Finance about the margin/price/cost bridge), so the domain agent does "
        "not decline it as out of scope.\n"
        "Output ONLY a JSON object, no prose:\n"
        '{"domains": ["FINANCE"|"SCM"|"COMMERCIAL", ...], '
        '"reasons": {"FINANCE": "<why this domain>", ...}, '
        '"subquestions": {"FINANCE": "<domain-specific question>", ...}}\n\n'
        f"Question: {question}"
    )


def _strip_json(raw: str) -> str:
    t = raw.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    return t.strip()


# Each domain's Genie space declines questions framed in another domain's terms (e.g. SCM
# declines a "margin" question). So for any domain whose subquestion is missing, we reframe the
# user's own question into that domain's language via a focused LLM call (below).
_REFRAME_HINT = {
    "FINANCE": "gross margin / price-per-unit / FX / COGS cost bridge (raw material, freight, energy)",
    "SCM": "OTIF, service level, backorders, stockouts, lane lead times (never use the word margin)",
    "COMMERCIAL": "at-risk accounts, churn score, complaints, NPS, account revenue trend",
}


def _reframe_subquestion(question: str, domain: str) -> str:
    """Reframe the user's question into the domain's own terms so its Genie space answers it
    rather than declining it as out of scope."""
    raw = dbx.chat(
        messages=[{"role": "user", "content": (
            f"The user asked: \"{question}\"\n\n"
            f"Rewrite it as a focused data question for the AkzoNobel {domain} analytics space, "
            f"which covers ONLY: {_REFRAME_HINT[domain]}. Keep the same subject/scope (e.g. Paints "
            f"EMEA, the relevant quarter/month) but ask ONLY for this domain's metrics. "
            "Output ONLY the rewritten question, one line, no preamble."
        )}],
        max_tokens=160,
    )
    return raw.strip().strip('"')


def route(question: str, descriptions: dict | None = None) -> dict:
    """NL question -> routing decision {domains, reasons, subquestions}. Domains chosen by the
    router; each chosen domain gets a subquestion reframed into its own terms."""
    descriptions = descriptions or ROUTING_DESCRIPTION
    raw = dbx.chat(
        messages=[{"role": "user", "content": _build_router_prompt(question, descriptions)}],
        max_tokens=900,
    )
    try:
        decision = json.loads(_strip_json(raw))
    except Exception:
        # Router parse fallback: consult all three rather than sink the turn.
        decision = {"domains": list(descriptions.keys()), "reasons": {}, "subquestions": {}}
    decision["domains"] = [d for d in decision.get("domains", []) if d in GENIE_PATHS]
    if not decision["domains"]:
        decision["domains"] = list(descriptions.keys())
    decision.setdefault("reasons", {})
    subqs = decision.get("subquestions") or {}
    # Ensure every chosen domain has a domain-framed subquestion. Finance handles margin/price/cost
    # questions natively, so it keeps the user's own question; SCM and Commercial decline questions
    # framed in finance terms, so they get a subquestion reframed into their own language.
    for d in decision["domains"]:
        if d == "FINANCE":
            subqs[d] = question  # Finance space answers margin/price/cost questions natively.
        elif not subqs.get(d):
            subqs[d] = _reframe_subquestion(question, d)
    decision["subquestions"] = subqs
    return decision


# ---------------------------------------------------------------------------
# LEG — invoke one domain subagent via the shared text2sql, pointed at that
# domain's genie space file. Runs the governed SQL on the warehouse (under the
# caller's UC identity in Apps / OBO). A failing leg degrades, never sinks.
# ---------------------------------------------------------------------------
def call_leg(domain: str, question: str, genie_w=None) -> dict:
    """One domain subagent: NL -> governed SQL -> rows. Returns a structured leg result.

    `question` should be the domain-specific subquestion (phrased in the domain's own terms)
    so the governed leg does not decline it as out of scope. `genie_w` is the OBO WorkspaceClient
    (the end user) used for the real Genie call; None falls back to the app service principal.
    """
    space_id = SPACE_IDS.get(domain, "")
    via, res = None, None
    # Prefer the REAL Genie space (under the end user's identity via OBO); if it errors, fall back to
    # the instruction-driven text2sql so the leg never goes dark.
    if space_id:
        try:
            res, via = _genie_leg(space_id, question, w=genie_w), "genie_space"
        except Exception:
            res, via = None, None
    if res is None:
        try:
            res, via = text2sql.ask(question, genie_instructions_path=GENIE_PATHS[domain]), "ai_query"
        except Exception as e:
            return {"domain": domain, "via": "error", "sql": "", "rows": [], "columns": [],
                    "row_count": 0, "error": str(e)[:300]}
    return {
        "domain": domain, "via": via, "sql": res["sql"], "rows": res["rows"][:50],
        "columns": res["columns"], "row_count": res["row_count"], "error": None,
    }


# ---------------------------------------------------------------------------
# FUSER — one LLM call: hand the chosen legs' structured rows (not free text) to
# the model and fuse ONE governed answer + ONE recommended action, grounded only
# in the retrieved numbers.
# ---------------------------------------------------------------------------
def fuse(question: str, decision: dict, legs: list[dict]) -> dict:
    evidence = json.dumps(
        {lr["domain"]: {"sql": lr["sql"], "rows": lr["rows"], "error": lr["error"]} for lr in legs},
        default=str,
    )
    prompt = (
        "You are the AkzoNobel Multi-Agent Supervisor. You consulted these domain subagents and got "
        "governed data.\n"
        f"Routing decision: {json.dumps(decision)}\n"
        f"Retrieved evidence (per domain, as JSON): {evidence}\n\n"
        "Fuse ONE answer to the user's question using ONLY the numbers above (do not invent figures). "
        "If multiple domains contributed, explicitly CONNECT them rather than listing them separately. "
        "Then give ONE concrete recommended action. If the data cannot answer the question, say so.\n\n"
        "Output ONLY a JSON object, no prose, no markdown fences:\n"
        '{"answer": "<= 200 words, the fused governed answer>", '
        '"recommended_action": "<one concrete next step>"}\n\n'
        f"User question: {question}"
    )
    raw = dbx.chat(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    try:
        parsed = json.loads(_strip_json(raw))
        return {
            "answer": parsed.get("answer", "").strip(),
            "recommended_action": parsed.get("recommended_action", "").strip(),
        }
    except Exception:
        # Fuser returned prose, not JSON — surface it as the answer.
        return {"answer": raw.strip(), "recommended_action": ""}


# ---------------------------------------------------------------------------
# SUPERVISE — full turn: route -> call chosen legs -> fuse -> persist to Lakebase
# ---------------------------------------------------------------------------
def ask(question: str, persona: str = "controller", user_token: str | None = None) -> dict:
    """Full supervisor turn. Returns routing trace, per-domain legs, fused answer +
    recommended action, the persona scope note, and the persisted session id/uuid.
    `user_token` is the end user's forwarded access token (OBO); when present, the Genie legs
    read under the caller's identity / row filters."""
    persona_info = PERSONAS.get(persona, PERSONAS["controller"])
    genie_w = _user_genie_client(user_token)

    decision = route(question)
    legs = [
        call_leg(d, decision["subquestions"].get(d) or question, genie_w=genie_w)
        for d in decision["domains"]
    ]
    fused = fuse(question, decision, legs)

    routing = [
        {"domain": d, "reason": decision["reasons"].get(d, "selected by router")}
        for d in decision["domains"]
    ]

    session_uuid = str(uuid.uuid4())
    session_id = _persist_session(session_uuid, question, decision["domains"], fused["answer"])

    return {
        "session_id": session_id,
        "session_uuid": session_uuid,
        "question": question,
        "persona": persona,
        "persona_scope": f"{persona_info['label']} — governed scope: {persona_info['scope']} "
        f"(OBO at the Genie-call layer, reads only).",
        "routing": routing,
        "legs": [
            {"domain": lr["domain"], "via": lr.get("via"), "sql": lr["sql"], "rows": lr["rows"],
             "columns": lr["columns"], "row_count": lr["row_count"], "error": lr["error"]}
            for lr in legs
        ],
        "answer": fused["answer"],
        "recommended_action": fused["recommended_action"],
    }


# ---------------------------------------------------------------------------
# LAKEBASE — memory (agent_sessions) + feedback (agent_feedback)
# ---------------------------------------------------------------------------
def _persist_session(session_uuid: str, question: str, domains: list[str], answer: str) -> int:
    """Log the supervisor turn to akzo.agent_sessions. Returns the new session_id."""
    row = lb.execute(
        """INSERT INTO agent_sessions (session_uuid, user_email, question, routed_domains, fused_answer)
           VALUES (%s, %s, %s, %s, %s) RETURNING session_id""",
        (session_uuid, dbx.current_user(), question, ",".join(domains), answer),
        returning=True,
    )
    return row["session_id"]


def record_feedback(session_uuid: str, rating: int, note: str | None = None) -> dict:
    """Write a thumbs up/down (+ optional note) to akzo.agent_feedback."""
    row = lb.execute(
        """INSERT INTO agent_feedback (session_uuid, user_email, rating, comment)
           VALUES (%s, %s, %s, %s) RETURNING feedback_id, created_at""",
        (session_uuid, dbx.current_user(), rating, note),
        returning=True,
    )
    return {"feedback_id": row["feedback_id"], "created_at": str(row["created_at"])}
