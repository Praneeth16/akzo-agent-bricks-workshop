# Databricks notebook source
# MAGIC %md
# MAGIC # Layer 6 — Trust: MLflow eval + an LLM judge
# MAGIC
# MAGIC *How you defend an agent to a controller. "No AI without measurable value."*
# MAGIC
# MAGIC This is the **reference build** behind the Layer-6 hands-on block. In the room you do not stand
# MAGIC any of this up — it is pre-staged. You **swap in one golden question and re-run the judge**.
# MAGIC This notebook shows exactly what that "one thing" is wired into.
# MAGIC
# MAGIC **The whole game (recap):** the Finance leg (Layer 1) answers *"why did Paints EMEA margin drop
# MAGIC in Q2 — price, volume, FX, or cost?"* A controller will not trust that answer because a chatbot
# MAGIC said so. **Trust comes from measurement:** we hold the agent to a fixed set of **golden
# MAGIC questions** with known-good answers, and grade every response with an **LLM judge** for
# MAGIC *correctness* and *groundedness*. The verdict, not the vibe, is what ships.
# MAGIC
# MAGIC **This layer, peeled, follows the 3-beat rhythm:**
# MAGIC 1. **See** — the 5 finance golden questions, the agent's answer to each, and a judge verdict.
# MAGIC 2. **Tweak** — swap in one golden question (edit its `expected_answer_contains`) and re-run the
# MAGIC    judge on just that case; watch the score move.
# MAGIC 3. **Return** — the eval set becomes a *gate*: the same agent is now measurable, and the
# MAGIC    supervisor's Finance leg can be regression-tested on every change.
# MAGIC
# MAGIC **What's governed here:** the golden set lives in `eval/finance.yaml` (the exact set the team
# MAGIC wrote in pre-read). Every run + every per-question verdict is logged to
# MAGIC `serverless_lakebase_praneeth_catalog.akzo_ops.eval_runs` and `.eval_results` in Unity Catalog —
# MAGIC so an eval is auditable, comparable across runs, and queryable by anyone with SELECT.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC We pin the catalog/schema, the agent's chat model, and a separate **judge** model. Using a
# MAGIC different model as the judge than the one being evaluated is good hygiene — the grader is not
# MAGIC marking its own homework.

# COMMAND ----------

CATALOG = "serverless_lakebase_praneeth_catalog"
FIN = f"{CATALOG}.akzo_finance"
OPS = f"{CATALOG}.akzo_ops"

AGENT_ENDPOINT = "databricks-claude-opus-4-7"          # the agent under test (same as Layer 1)
JUDGE_ENDPOINT = "databricks-gpt-5-5"                   # an independent grader
RUN_TAG = "layer6_finance_golden"

spark.sql(f"USE CATALOG {CATALOG}")
print("Finance schema:", FIN)
print("Ops schema    :", OPS)
print("Agent model   :", AGENT_ENDPOINT)
print("Judge model   :", JUDGE_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load the golden questions from `eval/finance.yaml`
# MAGIC
# MAGIC The eval set is **not** invented here — it is the same `eval/finance.yaml` the team authored in
# MAGIC pre-read. Each case carries the `question`, an `expected_answer_contains` list (the must-hit
# MAGIC facts), and `grading_notes` (what "good" vs "wrong" looks like) that we hand to the judge.

# COMMAND ----------

import os, yaml

# Resolve eval/finance.yaml whether the notebook runs from /Workspace, a Repo, or a local clone.
def _find_eval_yaml():
    candidates = [
        "../eval/finance.yaml",
        "./eval/finance.yaml",
        "/Workspace/Repos/akzo-workshop/agent-bricks-workshop/eval/finance.yaml",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

_path = _find_eval_yaml()
if _path:
    with open(_path) as f:
        GOLDEN = yaml.safe_load(f)
    print("Loaded golden set from:", _path)
else:
    # Inlined fallback so the notebook is self-contained if eval/ isn't on the path.
    print("eval/finance.yaml not found on path — using inlined copy.")
    GOLDEN = yaml.safe_load(r'''
track: finance
golden_questions:
  - id: q1
    question: "What happened to Paints EMEA gross margin in Q2 2026 versus Q1 2026?"
    expected_answer_contains: ["Q1 2026 ~39.6%", "Q2 2026 ~30.7%", "drop of ~8.9 percentage points", "Decorative Paints", "EMEA"]
    grading_notes: "Good: names the line (Decorative Paints), region (EMEA), both quarter margins (~39.6% -> ~30.7%) and the ~8.9pp drop. Wrong: quotes absolute EUR only, picks the wrong region/line, or reports a drop near the ~0.8pp baseline noise."
  - id: q2
    question: "Decompose the Paints EMEA Q2 2026 margin drop into price, volume, FX, and cost effects."
    expected_answer_contains: ["price erosion ~ -3pp", "realized price down ~3.5%", "adverse FX ~ -2pp", "raw-material spike ~ -3pp", "volume roughly flat"]
    grading_notes: "Good: four-way bridge summing to ~ -8pp, with price ~-3pp, FX ~-2pp, raw material ~-3pp, volume ~flat. Wrong: attributes the whole drop to one cause, omits FX, or claims a volume collapse."
  - id: q3
    question: "Which cost driver is responsible for the COGS increase in Paints EMEA in Q2 2026?"
    expected_answer_contains: ["raw material", "TiO2", "resin", "up ~15-20% in Q2", "freight/energy/overhead roughly stable"]
    grading_notes: "Good: isolates raw_material_cost (TiO2 + resin) up ~15-20% and notes the other three buckets are stable. Wrong: blames freight or energy, or cites total COGS without bucket decomposition."
  - id: q4
    question: "How much did adverse FX contribute to the Paints EMEA margin miss, and which currencies drove it?"
    expected_answer_contains: ["~ -2pp FX headwind", "EUR strengthened", "USD", "CNY", "~ -2.3% EUR-translation"]
    grading_notes: "Good: ~-2pp FX impact, names EUR strengthening vs USD/CNY (~-2.3% translation headwind). Wrong: ignores currency direction or double-counts FX as price erosion."
  - id: q5
    question: "Is the Q2 2026 margin problem specific to Paints EMEA or is it company-wide?"
    expected_answer_contains: ["specific to Decorative Paints in EMEA", "all other region x line combos stable", "max other swing ~0.79pp", "not company-wide"]
    grading_notes: "Good: confirms it is isolated to Decorative Paints x EMEA, every other segment < ~0.8pp Q1->Q2. Wrong: generalizes the drop or fails to compare against the stable baseline."
''')

QUESTIONS = GOLDEN["golden_questions"]
print(f"Golden questions: {len(QUESTIONS)}")
for q in QUESTIONS:
    print(f"  [{q['id']}] {q['question']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 1 — SEE: the agent answers each golden question
# MAGIC
# MAGIC We reuse the **Layer-1 text2SQL + reasoning pattern**: generate governed SQL from the question,
# MAGIC run it on serverless, then feed the retrieved numbers to the LLM for a controller-ready answer.
# MAGIC This is the same call the supervisor's Finance leg makes — we are evaluating the *real* agent,
# MAGIC not a toy.
# MAGIC
# MAGIC > We drive everything through `ai_query` on serverless so the notebook has no external deps. To
# MAGIC > evaluate the real Genie space instead, swap `agent_answer()` for a Genie Conversation API call.

# COMMAND ----------

import json, re

# The distilled Finance Genie instructions (same block as Layer 1) — the agent's system prompt.
FINANCE_INSTRUCTIONS = """You are the Akzo Finance text-to-SQL agent. Convert the user's question into ONE Spark SQL query.
Output ONLY the SQL, no prose, no markdown fences.

TABLES (all under serverless_lakebase_praneeth_catalog.akzo_finance):
- products(sku, product_name, product_line['Decorative Paints'|'Performance Coatings'], region['EMEA'|'Americas'|'APAC'|'China'], currency, list_price_eur, standard_cost_eur)
- margin_actuals(sku, region, month DATE, units, revenue_eur, cogs_eur, gross_margin_eur, gross_margin_pct)
- fx_rates(currency['EUR'|'USD'|'GBP'|'CNY'], month, rate_to_eur)
- cost_drivers(sku, region, month, raw_material_cost, freight_cost, energy_cost, overhead)

CERTIFIED RULES (always follow):
- gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur). NEVER average row-level gross_margin_pct.
- "Paints EMEA" := products.product_line='Decorative Paints' AND region='EMEA'. Join margin_actuals.sku=products.sku.
- Quarters 2026: Q1 = months 2026-01-01..2026-03-01 ; Q2 = months 2026-04-01..2026-06-01.
- month is a DATE at first-of-month; compare against 'YYYY-MM-01' literals.
- Currency is EUR. Round percentages to 1 decimal in SELECT.
- ALWAYS give every selected column a descriptive alias (AS ...). Return labeled dimension columns
  (quarter, product_line, region, cost-bucket names) alongside the measures so the result is
  self-describing — never emit bare unlabeled aggregates.
- For variance/decomposition or cost-driver questions, return Q1 AND Q2 side by side with separate
  columns for price_per_unit, raw_material_cost, freight_cost, energy_cost, overhead, units and
  gross_margin_pct so all four drivers (price/volume/FX/cost) are visible. Include fx_rates for USD/CNY
  when the question mentions FX or currencies."""


def _ai_query(endpoint: str, prompt: str) -> str:
    return spark.sql(
        "SELECT ai_query(:endpoint, :prompt) AS out",
        args={"endpoint": endpoint, "prompt": prompt},
    ).first()["out"]


def agent_answer(question: str) -> str:
    """The agent under test: text2SQL -> run on serverless -> reason over the numbers (Layer-1 pattern)."""
    # 1) NL -> governed SQL
    sql = _ai_query(AGENT_ENDPOINT, FINANCE_INSTRUCTIONS + "\n\nQ: " + question.replace("'", "''") + "\nSQL:").strip()
    if sql.startswith("```"):
        sql = sql.strip("`").lstrip("sql").strip()
    # 2) run it on serverless to get grounded evidence (labeled rows so the reasoner can read columns)
    try:
        rows = [r.asDict() for r in spark.sql(sql).limit(50).collect()]
        evidence = json.dumps(rows, default=str)
    except Exception as e:
        evidence = f"(SQL failed: {e}). SQL was: {sql}"
    # 3) reason over the numbers into a controller-ready answer. We pass the SQL too, so the column
    #    names tell the reasoner what each number means (a bare aggregate is uninterpretable).
    reason_prompt = (
        "You are a finance controlling copilot for AkzoNobel coatings. Using ONLY the data below "
        "(do not invent figures), answer the question concisely for a controller. Include the "
        "relevant margin %s, the percentage-point change, the named product line/region, and any "
        "price/volume/FX/cost drivers the data supports. The data is the result of this SQL, so the "
        f"column names tell you what each value means:\nSQL: {sql}\n\n"
        f"DATA (rows as JSON objects): {evidence}\n\nQUESTION: {question}\n\nANSWER:"
    )
    return _ai_query(AGENT_ENDPOINT, reason_prompt).strip()


# Generate the agent's answer for every golden question.
answers = {}
for q in QUESTIONS:
    answers[q["id"]] = agent_answer(q["question"])
    print(f"\n=== [{q['id']}] {q['question']}\n{answers[q['id']][:500]}")

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for above:** five blocks, one per golden question. Each shows the agent's
# MAGIC controller-ready answer (first 500 chars). Skim for the named figures — the Q1/Q2 margins, the
# MAGIC ~8.9pp drop, the price/FX/cost drivers. These are *unscored* right now; the judge in the next
# MAGIC cell is what turns "looks plausible" into a graded verdict.

# COMMAND ----------

# MAGIC %md
# MAGIC ### The LLM judge (correctness + groundedness)
# MAGIC
# MAGIC The judge is given the question, the **expected facts** (`expected_answer_contains`), the
# MAGIC **grading notes**, and the agent's answer. It returns strict JSON with a `correctness` and
# MAGIC `groundedness` score in `[0,1]`, a `pass` boolean, and a one-line rationale.
# MAGIC
# MAGIC - **Correctness** = does the answer hit the expected facts (right margins, right drivers, right
# MAGIC   scope)?
# MAGIC - **Groundedness** = is the answer supported by the retrieved numbers, with no invented figures?
# MAGIC
# MAGIC > **MLflow GenAI note:** newer DBR/MLflow ships `mlflow.genai.evaluate(...)` with built-in
# MAGIC > `Correctness`/`Groundedness` scorers. We use an `ai_query`-based judge here so the notebook runs
# MAGIC > on any MLflow version in the workshop fleet. The optional cell at the end shows the
# MAGIC > `mlflow.genai` path for workspaces that have it.

# COMMAND ----------

def judge(question: str, expected, grading_notes: str, answer: str) -> dict:
    expected_str = "\n".join(f"- {e}" for e in expected)
    prompt = f"""You are a strict evaluation judge for a finance copilot. Score the ANSWER against the EXPECTED FACTS.

QUESTION: {question}

EXPECTED FACTS (the answer should convey these; small wording/number rounding is fine):
{expected_str}

GRADING NOTES: {grading_notes}

ANSWER UNDER TEST:
{answer}

Return ONLY a JSON object, no prose, no markdown, with exactly these keys:
{{"correctness": <float 0..1>, "groundedness": <float 0..1>, "pass": <true|false>, "rationale": "<one sentence>"}}
- correctness: fraction of the expected facts the answer correctly conveys.
- groundedness: 1.0 if every claim is supported by data and no figures are invented, lower if it hallucinates.
- pass: true only if correctness >= 0.6 AND groundedness >= 0.6."""
    raw = _ai_query(JUDGE_ENDPOINT, prompt).strip()
    # be robust to fences / stray text around the JSON
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0) if m else raw)
    except Exception:
        v = {"correctness": 0.0, "groundedness": 0.0, "pass": False, "rationale": f"unparseable judge output: {raw[:200]}"}
    v["correctness"] = float(v.get("correctness", 0.0))
    v["groundedness"] = float(v.get("groundedness", 0.0))
    v["pass"] = bool(v.get("pass", False))
    return v


# Score every answer.
verdicts = {}
for q in QUESTIONS:
    verdicts[q["id"]] = judge(q["question"], q["expected_answer_contains"], q.get("grading_notes", ""), answers[q["id"]])
    v = verdicts[q["id"]]
    print(f"[{q['id']}] pass={v['pass']}  correctness={v['correctness']:.2f}  groundedness={v['groundedness']:.2f}  — {v['rationale']}")

pass_rate = sum(1 for v in verdicts.values() if v["pass"]) / len(verdicts)
print(f"\nPASS RATE: {pass_rate*100:.0f}%  ({sum(1 for v in verdicts.values() if v['pass'])}/{len(verdicts)})")

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for above:** one line per question with `pass`, `correctness`, and `groundedness`
# MAGIC in `[0,1]`, plus the **PASS RATE** at the bottom. A `pass=False` with high groundedness but low
# MAGIC correctness means the agent answered honestly from the data but missed an expected fact — exactly
# MAGIC the kind of gap the eval set exists to catch. The pass rate is the single number a controller cares
# MAGIC about: it is the agent's report card.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Persist the run to Unity Catalog (`eval_runs` + `eval_results`)
# MAGIC
# MAGIC An eval that lives only in a notebook output is not auditable. We write a one-row **run header**
# MAGIC to `akzo_ops.eval_runs` and one **row per question** to `akzo_ops.eval_results`, so any change to
# MAGIC the agent can be regression-compared run-over-run with a `SELECT`.

# COMMAND ----------

import uuid
from datetime import datetime, timezone

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {OPS}.eval_runs (
  run_id STRING, run_tag STRING, track STRING,
  agent_endpoint STRING, judge_endpoint STRING,
  n_questions INT, n_pass INT, pass_rate DOUBLE,
  avg_correctness DOUBLE, avg_groundedness DOUBLE,
  created_at TIMESTAMP
) USING DELTA
COMMENT 'MLflow-style eval run headers for Akzo agents (one row per eval run).'
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {OPS}.eval_results (
  run_id STRING, question_id STRING, question STRING,
  answer STRING, expected_facts STRING,
  correctness DOUBLE, groundedness DOUBLE, passed BOOLEAN,
  rationale STRING, created_at TIMESTAMP
) USING DELTA
COMMENT 'Per-question LLM-judge verdicts for Akzo agent evals (one row per question per run).'
""")

run_id = str(uuid.uuid4())
now = datetime.now(timezone.utc)
n = len(QUESTIONS)
n_pass = sum(1 for v in verdicts.values() if v["pass"])
avg_corr = sum(v["correctness"] for v in verdicts.values()) / n
avg_grnd = sum(v["groundedness"] for v in verdicts.values()) / n

# Run header
spark.createDataFrame(
    [(run_id, RUN_TAG, GOLDEN.get("track", "finance"), AGENT_ENDPOINT, JUDGE_ENDPOINT,
      n, n_pass, n_pass / n, avg_corr, avg_grnd, now)],
    schema="run_id string, run_tag string, track string, agent_endpoint string, judge_endpoint string, "
           "n_questions int, n_pass int, pass_rate double, avg_correctness double, avg_groundedness double, created_at timestamp",
).write.mode("append").saveAsTable(f"{OPS}.eval_runs")

# Per-question results
result_rows = []
for q in QUESTIONS:
    v = verdicts[q["id"]]
    result_rows.append((
        run_id, q["id"], q["question"], answers[q["id"]],
        " | ".join(q["expected_answer_contains"]),
        v["correctness"], v["groundedness"], v["pass"], v["rationale"], now,
    ))
spark.createDataFrame(
    result_rows,
    schema="run_id string, question_id string, question string, answer string, expected_facts string, "
           "correctness double, groundedness double, passed boolean, rationale string, created_at timestamp",
).write.mode("append").saveAsTable(f"{OPS}.eval_results")

print(f"Logged run {run_id}: {n_pass}/{n} pass, avg correctness {avg_corr:.2f}, avg groundedness {avg_grnd:.2f}")
display(spark.sql(f"SELECT question_id, ROUND(correctness,2) correctness, ROUND(groundedness,2) groundedness, passed, rationale FROM {OPS}.eval_results WHERE run_id = '{run_id}' ORDER BY question_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for above:** the `display` renders this run's per-question verdicts straight from
# MAGIC `eval_results` — proof the scores are now durable rows in Unity Catalog, not just notebook stdout.
# MAGIC The `run_id` ties the header in `eval_runs` to its detail rows; that join is what makes any future
# MAGIC regression diff a plain `SELECT`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 2 — TWEAK: swap in one golden question, re-run the judge
# MAGIC
# MAGIC **This is the live moment.** In the room you change *one* thing in the eval set and re-run the
# MAGIC judge on just that case. Two ways to tweak:
# MAGIC
# MAGIC 1. **Tighten an expectation** — add a fact the answer must contain (below we demand the answer
# MAGIC    name the ~8.9pp figure explicitly). A vaguer answer that passed before may now fail.
# MAGIC 2. **Swap the question** — point the agent at a different golden question and grade that.
# MAGIC
# MAGIC The cell below re-grades `q1` with a *stricter* expectation list — watch the score move without
# MAGIC touching the agent at all. That is the whole point: the eval is the contract, independent of the
# MAGIC model.

# COMMAND ----------

# >>> THIS IS THE LAYER YOU TWEAK <<< — edit TWEAK_QID or TWEAKED_EXPECTED and re-run this cell.
TWEAK_QID = "q1"
TWEAKED_EXPECTED = [
    "explicitly states ~39.6% in Q1",
    "explicitly states ~30.7% in Q2",
    "states the drop is ~8.9 percentage points (not just 'about 8%')",
    "names Decorative Paints AND EMEA",
]

tq = next(q for q in QUESTIONS if q["id"] == TWEAK_QID)
re_answer = agent_answer(tq["question"])             # re-ask the agent
re_verdict = judge(tq["question"], TWEAKED_EXPECTED,
                   "Stricter grading: the answer must state the exact figures, not approximations.",
                   re_answer)

print(f"[{TWEAK_QID}] re-graded under STRICTER expectations:")
print(f"  pass={re_verdict['pass']}  correctness={re_verdict['correctness']:.2f}  groundedness={re_verdict['groundedness']:.2f}")
print(f"  rationale: {re_verdict['rationale']}")
print(f"\nAnswer was:\n{re_answer[:600]}")

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for above:** compare `re_verdict` against this question's original verdict from
# MAGIC BEAT 1. If the same agent answer now scores lower (or flips to `pass=False`), you have shown the
# MAGIC eval is the lever — you raised the bar, not the model, and the gate tightened. That is the live
# MAGIC "aha" for the room.

# COMMAND ----------

# MAGIC %md
# MAGIC ## BEAT 3 — RETURN: the agent is now measurable (eval as a gate)
# MAGIC
# MAGIC The eval set is no longer a one-off — it is a **regression gate** the supervisor's Finance leg
# MAGIC runs on every change. Query `eval_runs` to compare runs over time; a drop in `pass_rate` blocks
# MAGIC a release. *"No AI without measurable value"* is now enforceable with a `SELECT`.

# COMMAND ----------

display(spark.sql(f"""
SELECT run_tag, agent_endpoint, judge_endpoint, n_pass, n_questions,
       ROUND(pass_rate*100,0) AS pass_pct,
       ROUND(avg_correctness,2) AS avg_correctness,
       ROUND(avg_groundedness,2) AS avg_groundedness,
       created_at
FROM {OPS}.eval_runs
ORDER BY created_at DESC
LIMIT 10
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for above:** the eval leaderboard — one row per run, newest first, with
# MAGIC `pass_pct`, `avg_correctness`, and `avg_groundedness`. After the BEAT-1 run plus the BEAT-2 re-run
# MAGIC you should see at least two rows; this is the run-over-run history a release process queries to
# MAGIC decide whether a change improved or regressed the Finance leg.

# COMMAND ----------

# MAGIC %md
# MAGIC ## OPTIONAL — facilitator-only: MemAlign judge-alignment teaser
# MAGIC
# MAGIC > **Do not make this a hands-on dependency.** Run it only if you have **version-verified** the
# MAGIC > MLflow GenAI API in *this* workspace at the Day-0 dry-run. Otherwise pre-record it.
# MAGIC
# MAGIC The point of MemAlign / judge-alignment: an LLM judge is only as good as its agreement with
# MAGIC **human labels**. With a handful of human-labeled examples ("this answer is good / this one is
# MAGIC wrong"), MLflow can *align* the judge so its verdicts track the controller's judgment, not the
# MAGIC model's default opinion. This is what turns "an LLM said it's fine" into "our judge agrees with
# MAGIC our experts 90% of the time."
# MAGIC
# MAGIC The cell is guarded — it no-ops cleanly if `mlflow.genai` is not present.

# COMMAND ----------

# FACILITATOR-ONLY. Guarded: skips cleanly if the API is absent. Never a hands-on step.
RUN_MEMALIGN_TEASER = False  # set True only after Day-0 version verification

if RUN_MEMALIGN_TEASER:
    try:
        import mlflow
        from mlflow.genai import judges  # noqa: F401
        print("mlflow.genai present — version:", mlflow.__version__)
        print("MemAlign path: collect a few human labels (good/wrong) on eval_results, then call the")
        print("judge-alignment optimizer so the judge's verdicts track human labels. Demo only.")
        # Sketch (API surface varies by version — verify before relying on it):
        #   from mlflow.genai.judges import make_judge
        #   aligned = make_judge(name="finance_correctness", instructions=...).align(human_labeled_df)
        #   mlflow.genai.evaluate(data=eval_df, scorers=[aligned])
    except Exception as e:
        print("mlflow.genai not available in this workspace — skipping MemAlign teaser. (", e, ")")
else:
    print("MemAlign teaser disabled (RUN_MEMALIGN_TEASER=False). Facilitator-only, version-verified.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## OPTIONAL — the `mlflow.genai.evaluate` path (if present in this workspace)
# MAGIC
# MAGIC On DBR/MLflow versions that ship the GenAI eval API, you can replace the hand-rolled judge above
# MAGIC with built-in scorers. Guarded so it never breaks the run.

# COMMAND ----------

USE_MLFLOW_GENAI = False  # flip True only where version-verified

if USE_MLFLOW_GENAI:
    try:
        import mlflow
        from mlflow.genai.scorers import Correctness, Guidelines  # names vary by version
        eval_data = [
            {"inputs": {"question": q["question"]},
             "outputs": answers[q["id"]],
             "expectations": {"expected_facts": q["expected_answer_contains"]}}
            for q in QUESTIONS
        ]
        results = mlflow.genai.evaluate(
            data=eval_data,
            scorers=[Correctness(), Guidelines(name="grounded", guidelines="No invented figures; supported by data.")],
        )
        print("mlflow.genai.evaluate complete:", results)
    except Exception as e:
        print("mlflow.genai.evaluate not available — using the ai_query judge above instead. (", e, ")")
else:
    print("mlflow.genai.evaluate path disabled — the ai_query judge above is the portable default.")

# COMMAND ----------

# MAGIC %md
# MAGIC **What we proved:**
# MAGIC - The Finance agent was held to the **5 golden questions** the team wrote, and an **independent
# MAGIC   LLM judge** scored every answer for **correctness + groundedness** — verdicts, not vibes.
# MAGIC - Every run + per-question verdict is in Unity Catalog (`akzo_ops.eval_runs` / `.eval_results`),
# MAGIC   so the agent is **auditable and regression-testable**.
# MAGIC - Tightening one expectation moved the score **without touching the model** — the eval set is
# MAGIC   the contract.
# MAGIC
# MAGIC **Next:** `07_ai_gateway_govern.py` — govern the model front-door at scale (routes, spend caps,
# MAGIC rate limits) with payload logging in UC.
