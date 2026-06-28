# Starter — Pricing & Quote Agent (adjacent track #18)

The densest act-end-to-end build: **parse an RFQ (`ai_extract`) → resolve to a SKU → price (list/cost/
margin, volume discount, margin guardrail) → draft → write to Lakebase `akzo.quotes` (pending) + open a
`quote_approvals` entry → approve.** Read → reason → act → write → approve.

## What's in this folder

| File | What it is |
|---|---|
| `starter.py` | Forkable Databricks notebook: `ai_extract` RFQ -> SKU match -> governed pricing -> draft -> Lakebase write (quotes + quote_approvals) -> approve, + a judge over the 5 golden questions. |
| `eval.yaml` | The 5 default golden questions + the failing case (copy of `eval/quote.yaml`). |
| `README.md` | This file. |

Pre-wired: `ai_extract` parse, the governed pricing call over `akzo_finance.products`, the Lakebase
write+approve pattern (`quotes` / `quote_approvals`), MLflow-style judge, sample-data refs, 5 golden
questions.

## Measurable value

Quote turnaround: manual RFQ-to-quote (find SKU, look up price, compute margin, draft) of **~30–45 min →
a parsed, priced, margin-checked draft staged for approval in 5–10 min.**

## Verified primary query (this workspace)

EMEA exterior product **DEC-1008 "Textured Exterior Coating"**: list **EUR 38.52**, std cost **EUR
22.82**, standard margin **40.8%**. At a 10% volume discount: net unit price **EUR 34.67**, post-discount
margin **34.2%** (above the 30% floor → OK to stage), extended price for 5,000 units **EUR 173,340**.

> Note: `eval/quote.yaml` q1 names "Dulux Weathershield Exterior Acrylic" as illustrative free text; the
> synthetic `products` table uses generic coating names, so the agent resolves it to the nearest EMEA
> exterior SKU (DEC-1008). Swap in your own catalog names in Sprint 1.

## 5 golden questions

1. Parse this RFQ ('…5,000 litres … EMEA … Rotterdam … net 30') — what did you extract?
2. What is the list price and standard cost for that product, and what unit margin does that imply?
3. Draft a quote for 5,000 units at a 10% volume discount and show the resulting margin.
4. Is this discounted price acceptable, or does it breach our margin guardrail?
5. Stage this quote for approval — what gets written and who approves?

(Full text + expected facts + failing case in `eval.yaml`.)

## Sprint 1 / 2 / 3 — tweak, swap, extend

Each sprint maps to a `# TODO (Day-2)` marker in `starter.py`.

- **Sprint 1 — TWEAK (parse).** `# TODO (Day-2) SPRINT 1` on `RFQ_TEXT` + the `ai_extract` field list.
  Swap in your inbound RFQ format and fields (add `incoterm`, `requested_delivery_date`, etc.), re-run.
- **Sprint 2 — SWAP (write/guardrail).** `# TODO (Day-2) SPRINT 2` on the `stage_quote` call. Change the
  margin floor, the discount source (e.g. a volume-tier table), or approval routing (auto-approve above
  floor, escalate below). Re-run and watch the row land.
- **Sprint 3 — EXTEND (eval).** `# TODO (Day-2) SPRINT 3` near the eval load. Add a golden question to
  `eval.yaml` (a multi-line RFQ or a tiered-discount case) and re-run the judge.

## Ship target

A working notebook + a Lakebase `quotes` + `quote_approvals` row (pending → approved). The full
deployable version is the React+FastAPI app with a human approval queue at **`apps/quote-agent/`** —
clone and deploy it, don't author it. This notebook is its logic spine.
