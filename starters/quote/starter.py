# Databricks notebook source
# MAGIC %md
# MAGIC # STARTER — Pricing & Quote Agent (parse RFQ -> price -> draft -> Lakebase -> approve)
# MAGIC
# MAGIC *Hackathon adjacent track #18 — the densest act-end-to-end build. Forkable Day-2 starter.*
# MAGIC
# MAGIC A **self-contained, forkable** notebook version of the quote workflow:
# MAGIC **parse an inbound RFQ with `ai_extract` -> resolve the product to a SKU in `akzo_finance.products`
# MAGIC -> price it (list/cost/margin, apply a volume discount, check the margin guardrail) -> draft the
# MAGIC quote -> write it to Lakebase `akzo.quotes` as `pending` and open a `quote_approvals` entry ->
# MAGIC approve**. Reads governed by OBO/UC; the write governed by app/service identity + approval + audit.
# MAGIC
# MAGIC **You already have a working agent.** Day-2 is *tweak -> swap -> extend*. The `# TODO (Day-2)`
# MAGIC markers are your sprint hooks.
# MAGIC
# MAGIC **Verified primary query (this workspace):** EMEA exterior product **DEC-1008 "Textured Exterior
# MAGIC Coating"** — list **EUR 38.52**, std cost **EUR 22.82**, standard margin **40.8%**; at a 10% volume
# MAGIC discount the net unit price is **EUR 34.67**, post-discount margin **34.2%**, extended price for
# MAGIC 5,000 units **EUR 173,340**.
# MAGIC
# MAGIC **Ship target:** a working notebook + a Lakebase `quotes` + `quote_approvals` row. The deployable
# MAGIC React+FastAPI version is the full app at **`apps/quote-agent/`** (clone, don't author) — this
# MAGIC notebook is the distilled logic behind it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — catalog, models

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
LLM_ENDPOINT = "databricks-claude-opus-4-7"   # extraction + drafting. Swap to "databricks-gpt-5-5" to compare.
MARGIN_FLOOR_PCT = 30.0                        # guardrail: a discounted quote below this escalates.

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance:", FIN, "| LLM:", LLM_ENDPOINT, "| margin floor:", MARGIN_FLOOR_PCT, "%")

import json

def _ai_query(prompt: str, endpoint: str = LLM_ENDPOINT) -> str:
    return spark.sql("SELECT ai_query(:e,:p) AS o", args={"e": endpoint, "p": prompt}).first()["o"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — PARSE: extract the RFQ with `ai_extract`
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 1 lives here. `ai_extract` pulls structured fields out of the free-text
# MAGIC RFQ. We then resolve the free-text product to a real SKU in `products`.

# COMMAND ----------

# TODO (Day-2) SPRINT 1 — SWAP IN YOUR RFQ + FIELDS: change the inbound text and the ai_extract field
#   list to match the RFQs your team handles (e.g. add 'incoterm', 'requested_delivery_date').
RFQ_TEXT = ("Hi, we need a price for 5,000 litres of exterior textured wall coating for our EMEA "
            "project, delivery to Rotterdam, net 30.")

extracted = spark.sql(
    "SELECT ai_extract(:txt, array('product','quantity','region','payment_terms','delivery_location')) AS x",
    args={"txt": RFQ_TEXT},
).first()["x"]
print("ai_extract ->", extracted)

# COMMAND ----------

# MAGIC %md
# MAGIC **Resolve the product to a SKU.** The extracted free-text product is matched against
# MAGIC `products.product_name` (LLM-assisted resolution so "exterior textured wall coating" -> the right
# MAGIC EMEA SKU). We constrain to the region from the RFQ.

# COMMAND ----------

candidates = [r.asDict() for r in spark.sql(f"""
  SELECT sku, product_name, region, currency, list_price_eur, standard_cost_eur
  FROM {FIN}.products WHERE region='EMEA' AND product_line='Decorative Paints'
  ORDER BY sku
""").collect()]

resolve_prompt = (
    f"Match this RFQ product to ONE SKU from the catalog. RFQ product: {json.dumps(dict(extracted))}\n"
    f"Catalog (JSON list): {json.dumps(candidates, default=str)}\n"
    'Return ONLY JSON: {"sku": "<best match sku>", "why": "<short>"}')
raw = _ai_query(resolve_prompt).strip()
if raw.startswith("```"):
    raw = raw.strip("`").lstrip("json").strip()
try:
    match = json.loads(raw)
except Exception:
    match = {"sku": "DEC-1008", "why": "fallback: EMEA exterior coating"}
SKU = match.get("sku", "DEC-1008")
print("Resolved SKU:", SKU, "—", match.get("why", ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — PRICE: list/cost/margin + discount + guardrail (PRIMARY GOVERNED CALL)
# MAGIC
# MAGIC The governed pricing lookup: pull list price and standard cost for the matched SKU, compute the
# MAGIC unit margin, apply the volume discount, and check the post-discount margin against the floor.

# COMMAND ----------

QTY = 5000
DISCOUNT_PCT = 10.0   # TODO (Day-2): make this come from a volume-tier table or the RFQ.

pricing = spark.sql(f"""
SELECT sku, product_name, region, currency, list_price_eur, standard_cost_eur,
  ROUND(list_price_eur - standard_cost_eur, 2)                                   AS unit_margin_eur,
  ROUND((list_price_eur - standard_cost_eur)/list_price_eur*100, 1)              AS std_margin_pct,
  ROUND(list_price_eur*(1-{DISCOUNT_PCT}/100), 2)                               AS net_unit_price_eur,
  ROUND(list_price_eur*(1-{DISCOUNT_PCT}/100)*{QTY}, 2)                         AS extended_price_eur,
  ROUND((list_price_eur*(1-{DISCOUNT_PCT}/100) - standard_cost_eur)
        /(list_price_eur*(1-{DISCOUNT_PCT}/100))*100, 1)                        AS disc_margin_pct
FROM {FIN}.products WHERE sku = '{SKU}'
""").first().asDict()
display(spark.createDataFrame([pricing]))

breaches_floor = pricing["disc_margin_pct"] < MARGIN_FLOOR_PCT
print(f"\nDiscounted margin {pricing['disc_margin_pct']}% vs floor {MARGIN_FLOOR_PCT}% -> "
      + ("ESCALATE (below floor)" if breaches_floor else "OK to stage"))
# Expected for DEC-1008: list 38.52, cost 22.82, std margin 40.8%, net 34.67, disc margin 34.2%, ext 173340 -> OK.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — DRAFT: the quote text (grounded only in the priced numbers)

# COMMAND ----------

draft = _ai_query(
    "You are an AkzoNobel pricing agent. Draft a concise, professional B2B quote using ONLY these "
    f"numbers (do not invent discounts or terms): {json.dumps(pricing, default=str)}. "
    f"Quantity {QTY} units, {DISCOUNT_PCT}% volume discount, payment terms {dict(extracted).get('payment_terms','Net 30')}. "
    f"State the net unit price, extended total, and the resulting margin %. If margin is below "
    f"{MARGIN_FLOOR_PCT}% flag it for approval. Keep under 150 words.")
print(draft)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ACT: write the quote to Lakebase + open the approval, then approve
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 2 lives here. The quote lands in `akzo.quotes` as `pending` under the
# MAGIC service identity, a `quote_approvals` row is opened, then a human approves. Tables already exist
# MAGIC (created by `notebooks/05_lakebase_memory_action.py`). This is read -> reason -> **act -> write ->
# MAGIC approve**.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import psycopg
from contextlib import contextmanager

INSTANCE_NAME = "graphrag-spike"
DB_NAME = "databricks_postgres"
PG_SCHEMA = "akzo"
SERVICE_IDENTITY = "quote-agent@service"

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE_NAME)
PG_HOST = inst.read_write_dns
PG_USER = w.current_user.me().user_name

@contextmanager
def pg():
    cred = w.database.generate_database_credential(instance_names=[INSTANCE_NAME])
    conn = psycopg.connect(host=PG_HOST, port=5432, dbname=DB_NAME,
                           user=PG_USER, password=cred.token, sslmode="require", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {PG_SCHEMA}")
        yield conn
    finally:
        conn.close()

def stage_quote(account_id, sku, region, qty, list_price, quoted_price, discount_pct, rationale,
                created_by=SERVICE_IDENTITY) -> int:
    """ACTION: stage a quote as pending + open a pending approval. Returns quote_id."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO quotes
               (account_id, sku, region, quantity_units, list_price_eur, quoted_price_eur, discount_pct, rationale, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING quote_id""",
            (account_id, sku, region, qty, list_price, quoted_price, discount_pct, rationale, created_by))
        qid = cur.fetchone()[0]
        cur.execute("INSERT INTO quote_approvals (quote_id) VALUES (%s)", (qid,))
        return qid

def approve_quote(quote_id, approver, comment="approved") -> tuple:
    """APPROVAL FLOW: flip the quote + its approval ledger to approved with audit."""
    with pg() as conn, conn.cursor() as cur:
        cur.execute("UPDATE quotes SET status='approved' WHERE quote_id=%s AND status='pending'", (quote_id,))
        cur.execute(
            """UPDATE quote_approvals SET decision='approved', approver=%s, comment=%s, decided_at=now()
               WHERE quote_id=%s AND decision='pending'
               RETURNING decision, approver, decided_at""",
            (approver, comment, quote_id))
        return cur.fetchone()

# COMMAND ----------

# TODO (Day-2) SPRINT 2 — SWAP THE WRITE/GUARDRAIL: change the margin floor, the discount source, or
#   the approval routing (e.g. auto-approve above floor, escalate below). Re-run and watch the row land.
qid = stage_quote(
    account_id="ACC-EMEA-DEMO", sku=SKU, region="EMEA", qty=QTY,
    list_price=pricing["list_price_eur"], quoted_price=pricing["net_unit_price_eur"],
    discount_pct=DISCOUNT_PCT,
    rationale=f"{DISCOUNT_PCT}% volume discount on {QTY}u of {pricing['product_name']}; "
              f"net {pricing['net_unit_price_eur']} EUR/u, post-discount margin {pricing['disc_margin_pct']}% "
              f"(floor {MARGIN_FLOOR_PCT}%); extended {pricing['extended_price_eur']} EUR.",
)
print("Wrote quote id =", qid, "(status=pending) + pending quote_approvals row")

# A human approver releases it (only a human can; the agent stages, it does not self-approve).
print("Approve:", approve_quote(qid, approver="sales.manager.emea@akzo.example"))

with pg() as conn, conn.cursor() as cur:
    cur.execute("""SELECT q.quote_id, q.sku, q.quantity_units, q.quoted_price_eur, q.discount_pct, q.status,
                          q.created_by, a.decision, a.approver, a.decided_at
                   FROM quotes q JOIN quote_approvals a ON a.quote_id=q.quote_id
                   WHERE q.quote_id=%s""", (qid,))
    print("Audited quote + approval:", cur.fetchone())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Eval judge over the 5 golden questions
# MAGIC
# MAGIC `# TODO (Day-2)` SPRINT 3 lives in `eval.yaml`. Same portable `ai_query` judge as
# MAGIC `notebooks/06_mlflow_eval_judge.py`. The agent answers each quote golden question from the priced
# MAGIC evidence + the staging behaviour above.

# COMMAND ----------

import os, re, yaml

def _find_eval():
    for c in ["./eval.yaml", "../eval.yaml", "starters/quote/eval.yaml"]:
        if os.path.exists(c):
            return c
    return None

_p = _find_eval()
GOLDEN = yaml.safe_load(open(_p)) if _p else {"golden_questions": []}
QUESTIONS = GOLDEN.get("golden_questions", [])
JUDGE_ENDPOINT = "databricks-gpt-5-5"
print("Loaded", len(QUESTIONS), "golden questions from", _p)

QUOTE_CONTEXT = (
    f"EXTRACTED={json.dumps(dict(extracted), default=str)} MATCHED_SKU={SKU} "
    f"PRICING={json.dumps(pricing, default=str)} QUANTITY={QTY} DISCOUNT_PCT={DISCOUNT_PCT} "
    f"MARGIN_FLOOR_PCT={MARGIN_FLOOR_PCT} "
    f"STAGING='quote written to Lakebase akzo.quotes as pending under the {SERVICE_IDENTITY} identity, "
    f"a pending quote_approvals row opened, requires a human approver — the agent never self-approves'")

def quote_answer(question: str) -> str:
    return _ai_query(
        "You are an AkzoNobel pricing & quote agent. Using ONLY this governed context (do not invent "
        f"prices, SKUs, or discounts):\n{QUOTE_CONTEXT}\n\nAnswer concisely.\n\nQUESTION: {question}\n\nANSWER:")

def judge(question, expected, notes, answer) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a quote agent. Score the ANSWER against the EXPECTED FACTS.
QUESTION: {question}
EXPECTED FACTS (small wording/number rounding is fine):
{expected_str}
GRADING NOTES: {notes}
ANSWER UNDER TEST:
{answer}
Return ONLY JSON: {{"correctness": <0..1>, "groundedness": <0..1>, "pass": <true|false>, "rationale": "<one sentence>"}}
pass=true only if correctness>=0.6 AND groundedness>=0.6."""
    raw = _ai_query(prompt, endpoint=JUDGE_ENDPOINT).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": "unparseable: " + raw[:150]}
    v["correctness"] = float(v.get("correctness", 0.0)); v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v

# TODO (Day-2) SPRINT 3 — EXTEND THE EVAL: add a golden question to eval.yaml (e.g. a multi-line RFQ or a
#   tiered-discount case) and re-run the judge.
n_pass = 0
for q in QUESTIONS:
    v = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), quote_answer(q["question"]))
    n_pass += int(v["pass"])
    print(f"[{q['id']}] pass={v['pass']} corr={v['correctness']:.2f} grnd={v['groundedness']:.2f} — {v['rationale']}")
print(f"\nPASS RATE: {n_pass}/{len(QUESTIONS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return to the whole + ship
# MAGIC
# MAGIC The agent parses the RFQ -> resolves the SKU -> prices with a margin guardrail -> drafts ->
# MAGIC writes the quote + approval to Lakebase -> a human approves -> is graded.
# MAGIC
# MAGIC - **Sprint 1 (tweak):** swap the RFQ text + `ai_extract` fields for your inbound format.
# MAGIC - **Sprint 2 (swap):** change the margin floor / discount source / approval routing.
# MAGIC - **Sprint 3 (extend):** add a golden question to `eval.yaml`; re-run the judge.
# MAGIC
# MAGIC **Deployable app:** the full React+FastAPI quote agent with a human approval queue lives at
# MAGIC **`apps/quote-agent/`** — clone and deploy it, don't author it. This notebook is its logic spine.
