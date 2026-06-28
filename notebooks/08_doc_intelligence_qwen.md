# Layer 8 — Document Intelligence with the latest AI functions (+ Qwen embeddings)

Companion notes for `notebooks/08_doc_intelligence_qwen.py`. This records which approach
actually worked when the pipeline was run end-to-end against the
`fe-vm-lakebase-praneeth` workspace, the Vector Search endpoint/index used, and the
extraction accuracy versus ground truth.

## Source documents

- Volume: `/Volumes/serverless_lakebase_praneeth_catalog/akzo_docs/raw/`
  - `sds/*.pdf` — 8 Safety Data Sheets
  - `contracts/*.pdf` — 6 supplier contracts
- Ground truth: `data/output/docs/README.md`

## Approach that worked: native `ai_*`, no chat-model fallback

Every parse / classify / extract step ran on the **native `ai_*` functions**. No
`ai_query`-with-chat-model fallback was required.

| Step | Function | Native or fallback | Notes |
|---|---|---|---|
| 1. Parse | `ai_parse_document(content)` | **Native** | Returns a `VARIANT`; navigate with `:` (`parsed:document:elements`). Tables come back as HTML. |
| 2. Classify | `ai_classify(text, ARRAY('SDS','contract'))` | **Native** | Classified on first 2000 chars. |
| 3. Extract | `ai_extract(text, ARRAY(...))` | **Native** | Returns a `STRUCT`; navigate with dot notation (`j.product`), not `:`. |
| 5. Embed | `ai_query('databricks-qwen3-embedding-0-6b', text, returnType => 'ARRAY<FLOAT>')` | n/a | `ai_query` is the supported way to call an embedding endpoint from SQL. 1024-dim. |
| 7. RAG answer | `ai_query('databricks-claude-opus-4-7', prompt)` | n/a | Grounded on retrieved chunks. |

### Two gotchas worth remembering

- `ai_parse_document` returns **`VARIANT`**, so `parse_json`/`try_parse_json` on its
  output fails with `DATATYPE_MISMATCH` — use the `:` accessor directly.
- `ai_extract` returns a **`STRUCT`**, not a JSON string, so the `:` JSON accessor fails
  (`semi_structured_extract_json_multi` error) — use dot notation (`j.supplier`).

## Tables created

| Table | Rows |
|---|---|
| `akzo_docs.docs_parsed` | 14 |
| `akzo_docs.docs_classified` | 14 |
| `akzo_docs.sds_extracted` | 8 |
| `akzo_docs.contracts_extracted` | 6 |
| `akzo_docs.chunks` | 50 |
| `akzo_docs.chunks_embedded` (CDF enabled, 1024-dim `embedding`) | 50 |

## Vector Search

- Endpoint: **`akzo_workshop_vs`** (STANDARD, ONLINE) — created fresh for the workshop.
- Index: **`serverless_lakebase_praneeth_catalog.akzo_docs.chunks_idx`**
  - Type: `DELTA_SYNC`, `TRIGGERED`
  - Embeddings: **self-managed** — points at the precomputed `embedding` column
    (Qwen, 1024-dim) on `chunks_embedded`.
  - Primary key: `chunk_id`.
  - Status reached: **READY**.

## Extraction accuracy vs ground truth

- **Classification: 14/14 = 100%** — every doc's `ai_classify` label matched its folder.
- **SDS (8 docs): 100% on the key fields** — `product`, `hazard_class`, `voc_g_per_l`,
  `storage_temp`, and `ppe` all match `data/output/docs/README.md`. `flash_point_c` is
  correctly `NULL` for the three powder / water-based products that have no flash point in
  ground truth ("N/A"), and matches exactly for the five flammable liquids (23, 31, 27,
  62, plus the solvent basecoat).
- **Contracts (6 docs): 100%** — `supplier`, `annual_spend_eur`, `payment_terms_days`,
  `price_escalation_clause`, and `termination_notice_days` all match ground truth for all
  six contracts, including the two flagged ones.

## Semantic search + RAG (Step 7)

Query: **"titanium dioxide storage and PPE requirements"**, embedded with the same Qwen
endpoint and run against `chunks_idx`. Top-5 retrieved chunks (all SDS, as expected):

| rank | score | doc_id | content |
|---|---|---|---|
| 1 | 0.611 | sds_an_0455 | Section 8 exposure controls / PPE |
| 2 | 0.607 | sds_an_2204 | "Titanium dioxide (rutile)" 5-10%, Carc. 2 (inhalable dust) |
| 3 | 0.603 | sds_an_0419 | Section 8 exposure controls / PPE |
| 4 | 0.603 | sds_an_0413 | Section 8 exposure controls / PPE |
| 5 | 0.600 | sds_an_3301 | "Titanium dioxide (rutile)" 8-15%, Carc. 2 (inhalable dust) |

The `databricks-claude-opus-4-7` RAG answer, grounded only on those chunks, correctly
returned TiO2 storage temperatures (5-35 C / 5-30 C), per-product PPE (FFP2/FFP3 dust
masks, nitrile gloves, goggles, anti-static footwear, A2 respirator), engineering controls
(local exhaust ventilation), and the **Carc. 2 (inhalable dust)** classification — every
fact cited back to its source `doc_id`.

## Fusion query result

`SELECT ... FROM contracts_extracted WHERE payment_terms_days > 60 AND annual_spend_eur > 1000000`
returns **exactly the two expected suppliers**:

| supplier | category | annual_spend_eur | payment_terms_days |
|---|---|---|---|
| Tronox Pigments (Holland) B.V. | Titanium Dioxide (TiO2) Pigment Supply | 4,250,000 | 90 |
| Allnex Netherlands B.V. | Resin Supply (Polyester and Acrylic Resins) | 2,900,000 | 120 |
