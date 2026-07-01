# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC Step 6 uses the Vector Search Python client, not preinstalled on every serverless image. Install it,
# MAGIC then restart Python. (Run this cell first; it is the only `%pip` in the notebook.)

# COMMAND ----------

# MAGIC %pip install --quiet databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 5 — Document intelligence
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH1 Supervisor  CH2 Agents that act  CH3 Autonomous loop  CH4 Trust & governance  CH5 Documents  ← here
# MAGIC ```
# MAGIC
# MAGIC Take a pile of **raw PDFs in a Unity Catalog volume** — 8 Safety Data Sheets + 6 supplier contracts —
# MAGIC and turn them into **governed, queryable intelligence** with no model-serving glue. Everything runs as
# MAGIC SQL on serverless using the native `ai_*` functions, plus **Qwen** embeddings + **Vector Search**.
# MAGIC
# MAGIC ```
# MAGIC   PDFs ─▶ ai_parse_document ─▶ ai_classify ─▶ ai_extract ─▶ chunk ─▶ Qwen embed ─▶ Vector Search index
# MAGIC   (volume)   docs_parsed        docs_classified  sds/contracts   chunks   chunks_embedded   chunks_idx
# MAGIC                                                       │                                         │
# MAGIC                          ┌────────────────────────────┘                                         ▼
# MAGIC                          ▼                                                          semantic search + RAG
# MAGIC                  SQL over extracted fields  ◀── one governed source answers both ──▶  grounded answer
# MAGIC                  "non-standard suppliers?"      structured AND unstructured Q&A       "TiO2 PPE/storage?"
# MAGIC ```
# MAGIC
# MAGIC **The whole game:** a compliance/procurement analyst asks both *"what PPE and storage does titanium
# MAGIC dioxide need?"* (unstructured → RAG over SDS text) **and** *"which suppliers have non-standard payment
# MAGIC terms on big spend?"* (structured → SQL over extracted fields) — over the **same documents**, in the
# MAGIC **same governed catalog**.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - The 14 PDFs in the volume `/Volumes/<catalog>/akzo_docs/raw/{sds,contracts}/*.pdf`.
# MAGIC - A Qwen embedding endpoint, a chat model, and permission to create a Vector Search endpoint/index.
# MAGIC
# MAGIC ### How to run (~15 min)
# MAGIC Top-to-bottom. Step 6 blocks until the index reaches READY (can take a few minutes on first build).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters
# MAGIC
# MAGIC Native parse/classify/extract need no fallback. Embeddings call the Qwen endpoint from SQL via
# MAGIC `ai_query(..., returnType => 'ARRAY<FLOAT>')` (the supported way to call an embedding model from SQL).

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Unity Catalog (blank = current_catalog())")
dbutils.widgets.text("embed_endpoint", "databricks-qwen3-embedding-0-6b", "Qwen embedding endpoint")
dbutils.widgets.text("chat_endpoint", "databricks-claude-opus-4-8", "RAG chat model")
dbutils.widgets.text("vs_endpoint", "akzo_workshop_vs", "Vector Search endpoint")

CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "akzo_docs"
DOCS = f"{CATALOG}.{SCHEMA}"
VOLUME_GLOB = f"/Volumes/{CATALOG}/{SCHEMA}/raw/*/*.pdf"
EMBED_ENDPOINT = dbutils.widgets.get("embed_endpoint")
CHAT_ENDPOINT = dbutils.widgets.get("chat_endpoint")
VS_ENDPOINT = dbutils.widgets.get("vs_endpoint")
VS_INDEX = f"{DOCS}.chunks_idx"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {DOCS}")
print("Docs schema:", DOCS, "| Embed:", EMBED_ENDPOINT, "| Chat:", CHAT_ENDPOINT)
print("VS endpoint:", VS_ENDPOINT, "| VS index:", VS_INDEX)
print("Source PDFs:", VOLUME_GLOB)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Parse: `ai_parse_document` over the raw PDFs
# MAGIC
# MAGIC `ai_parse_document` is the document OCR/layout function. We read PDF bytes with
# MAGIC `READ_FILES(..., format => 'binaryFile')` and hand `content` to it. It returns a **VARIANT** with a
# MAGIC structured `document.elements[]` array (titles, headers, paragraphs, **tables as HTML**). We flatten
# MAGIC the element `content` into one `parsed_text` per document. (Navigate VARIANT with the `:` accessor.)

# COMMAND ----------

spark.sql(rf"""
CREATE OR REPLACE TABLE {DOCS}.docs_parsed AS
WITH raw AS (
  SELECT
    regexp_extract(path, '([^/]+)\\.pdf$', 1) AS doc_id,
    path,
    CASE WHEN path LIKE '%/sds/%' THEN 'SDS' ELSE 'contract' END AS doc_type_guess,
    ai_parse_document(content) AS parsed
  FROM READ_FILES('{VOLUME_GLOB}', format => 'binaryFile')
)
SELECT
  doc_id, path, doc_type_guess,
  array_join(
    transform(
      from_json(CAST(parsed:document:elements AS STRING), 'ARRAY<STRUCT<content:STRING,type:STRING>>'),
      e -> e.content
    ), '\n'
  ) AS parsed_text
FROM raw
""")
display(spark.sql(f"SELECT doc_id, doc_type_guess, length(parsed_text) AS parsed_chars FROM {DOCS}.docs_parsed ORDER BY doc_type_guess, doc_id"))
# Look for: all 14 doc_ids present, parsed_chars in the thousands (near-zero = a scanned/empty PDF).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Classify: `ai_classify` labels each document
# MAGIC
# MAGIC `ai_classify(text, ARRAY('SDS','contract'))` returns the best-fit label from the candidate set — a
# MAGIC zero-config classifier with no training data. We classify on the first ~2000 chars; the `doc_type`
# MAGIC drives which extraction schema each doc gets. `agrees` should be `true` for all 14 (verified 14/14).

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {DOCS}.docs_classified AS
SELECT doc_id, path, doc_type_guess, parsed_text,
       ai_classify(substr(parsed_text, 1, 2000), ARRAY('SDS','contract')) AS doc_type
FROM {DOCS}.docs_parsed
""")
display(spark.sql(f"SELECT doc_id, doc_type_guess, doc_type, (doc_type_guess = doc_type) AS agrees FROM {DOCS}.docs_classified ORDER BY doc_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Extract: `ai_extract` pulls structured fields
# MAGIC
# MAGIC `ai_extract(text, ARRAY(<field names>))` returns a **STRUCT** with one field per requested name
# MAGIC (navigate with dot notation). Two schemas, gated on the Step-2 label. For contracts we normalise to
# MAGIC typed columns and compute the business rule **`non_standard_flag = payment_terms_days > 60 AND
# MAGIC annual_spend_eur > 1,000,000`** right in SQL.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {DOCS}.sds_extracted AS
WITH ex AS (
  SELECT doc_id,
    ai_extract(parsed_text, ARRAY('product','hazard_class','flash_point_c','voc_g_per_l','storage_temp','ppe')) AS j
  FROM {DOCS}.docs_classified WHERE doc_type = 'SDS'
)
SELECT doc_id, j.product AS product, j.hazard_class AS hazard_class, j.flash_point_c AS flash_point_c,
       j.voc_g_per_l AS voc_g_per_l, j.storage_temp AS storage_temp, j.ppe AS ppe
FROM ex
""")
display(spark.sql(f"SELECT doc_id, product, hazard_class, flash_point_c, voc_g_per_l, storage_temp FROM {DOCS}.sds_extracted ORDER BY doc_id"))

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {DOCS}.contracts_extracted AS
WITH ex AS (
  SELECT doc_id,
    ai_extract(parsed_text, ARRAY('supplier','category','annual_spend_eur','payment_terms_days',
              'price_escalation_clause','termination_notice_days')) AS j
  FROM {DOCS}.docs_classified WHERE doc_type = 'contract'
)
SELECT doc_id,
  j.supplier AS supplier, j.category AS category,
  CAST(regexp_replace(j.annual_spend_eur, '[^0-9]', '') AS BIGINT)      AS annual_spend_eur,
  CAST(regexp_replace(j.payment_terms_days, '[^0-9]', '') AS INT)       AS payment_terms_days,
  (lower(j.price_escalation_clause) IN ('true','yes'))                  AS price_escalation_clause,
  CAST(regexp_replace(j.termination_notice_days, '[^0-9]', '') AS INT)  AS termination_notice_days,
  ( CAST(regexp_replace(j.payment_terms_days, '[^0-9]', '') AS INT) > 60
    AND CAST(regexp_replace(j.annual_spend_eur, '[^0-9]', '') AS BIGINT) > 1000000 ) AS non_standard_flag
FROM ex
""")
display(spark.sql(f"""SELECT doc_id, supplier, annual_spend_eur, payment_terms_days, price_escalation_clause,
                      termination_notice_days, non_standard_flag FROM {DOCS}.contracts_extracted ORDER BY annual_spend_eur DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Auto-chunk the parsed text
# MAGIC
# MAGIC Split each `parsed_text` into ~500-token (~2000-char) windows stepping by 1600 chars (~400-char /
# MAGIC ~100-token overlap) so a fact straddling a boundary still lands whole in one chunk. We carry
# MAGIC `doc_type` so the index can be filtered by SDS vs contract later.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {DOCS}.chunks AS
WITH base AS (
  SELECT doc_id, doc_type, parsed_text,
         sequence(0, GREATEST(CAST(CEIL(length(parsed_text)/1600.0) AS INT) - 1, 0)) AS idxs
  FROM {DOCS}.docs_classified
),
exploded AS (
  SELECT doc_id, doc_type, parsed_text, posexplode(idxs) AS (seq, _i) FROM base
)
SELECT concat(doc_id, '_', lpad(CAST(seq AS STRING), 3, '0')) AS chunk_id,
       doc_id, doc_type, substr(parsed_text, seq*1600 + 1, 2000) AS chunk_text
FROM exploded
WHERE length(substr(parsed_text, seq*1600 + 1, 2000)) > 0
""")
display(spark.sql(f"SELECT count(*) AS n_chunks, count(DISTINCT doc_id) AS n_docs, round(avg(length(chunk_text))) AS avg_chunk_chars FROM {DOCS}.chunks"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Embed with Qwen (`databricks-qwen3-embedding-0-6b`)
# MAGIC
# MAGIC Embed each chunk via `ai_query(<endpoint>, chunk_text, returnType => 'ARRAY<FLOAT>')` — Qwen3
# MAGIC returns a **1024-dim** vector. We enable **Change Data Feed** on the output table — the prerequisite
# MAGIC for a delta-sync Vector Search index to track inserts incrementally. `min_dim`/`max_dim` must both be
# MAGIC 1024.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {DOCS}.chunks_embedded
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
SELECT chunk_id, doc_id, doc_type, chunk_text,
       ai_query('{EMBED_ENDPOINT}', chunk_text, returnType => 'ARRAY<FLOAT>') AS embedding
FROM {DOCS}.chunks
""")
display(spark.sql(f"SELECT count(*) AS n_rows, min(size(embedding)) AS min_dim, max(size(embedding)) AS max_dim FROM {DOCS}.chunks_embedded"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Vector Search delta-sync index
# MAGIC
# MAGIC A self-managed-embeddings delta-sync index over `chunks_embedded`, pointing at the `embedding`
# MAGIC column (so Vector Search stores our Qwen vectors rather than re-embedding). Idempotent: creates the
# MAGIC endpoint + index if missing, then blocks until the index reports `ready=True`.

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient
import time

vsc = VectorSearchClient(disable_notice=True)
try:
    vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
    print("Creating endpoint", VS_ENDPOINT)
except Exception as e:
    print("Endpoint exists / in progress:", str(e)[:120])
try:
    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT, index_name=VS_INDEX, source_table_name=f"{DOCS}.chunks_embedded",
        pipeline_type="TRIGGERED", primary_key="chunk_id", embedding_dimension=1024,
        embedding_vector_column="embedding")
    print("Creating index", VS_INDEX)
except Exception as e:
    print("Index exists / in progress:", str(e)[:120])

idx = vsc.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
try:
    idx.sync()
except Exception as e:
    print("sync:", str(e)[:120])
for _ in range(60):
    st = idx.describe().get("status", {})
    print(st.get("detailed_state"), "ready=", st.get("ready"), "indexed_rows=", st.get("indexed_row_count"))
    if st.get("ready"):
        break
    time.sleep(15)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Semantic search + grounded RAG answer
# MAGIC
# MAGIC Embed the query with the **same Qwen endpoint** (keep query + document vectors in one space), search
# MAGIC the index for the top-k chunks, then hand them to the chat model with a strict instruction: answer
# MAGIC **only** from the retrieved context and **cite the `doc_id`** of every fact. This is the pattern an
# MAGIC agent's "search the documents" tool calls under the hood.

# COMMAND ----------

QUESTION = "titanium dioxide storage and PPE requirements"
qvec = spark.sql("SELECT ai_query(:ep, :q, returnType => 'ARRAY<FLOAT>') AS v",
                 args={"ep": EMBED_ENDPOINT, "q": QUESTION}).collect()[0]["v"]

idx = vsc.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
# The index can report ready=True from describe() a few seconds before the query path
# accepts requests, so the first search may raise "index ... is not ready". Retry briefly.
for attempt in range(8):
    try:
        res = idx.similarity_search(query_vector=list(qvec),
                                    columns=["chunk_id", "doc_id", "doc_type", "chunk_text"], num_results=5)
        break
    except Exception as e:
        if "not ready" not in str(e) or attempt == 7:
            raise
        print("index not queryable yet, retrying...")
        time.sleep(15)
rows = res["result"]["data_array"]
print("Top-k retrieved chunks:")
for r in rows:
    print(f"  score={r[-1]:.3f}  doc_id={r[1]}  chunk_id={r[0]}")
context = "\n\n---\n".join([f"[{r[1]}] {r[3]}" for r in rows])

prompt = f"""You are a chemical-safety assistant. Answer the question using ONLY the context below.
Cite the doc_id in square brackets after each fact. If the context does not contain the answer, say so.

Question: {QUESTION}

Context:
{context}
"""
answer = spark.sql("SELECT ai_query(:ep, :p) AS a", args={"ep": CHAT_ENDPOINT, "p": prompt}).collect()[0]["a"]
print("\n" + answer)
# Look for: TiO2 storage + PPE described, each fact tagged with a traceable [doc_id]; refusal if not in context.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 8 — Structured + unstructured fusion
# MAGIC
# MAGIC The structured half, over the **same documents**. *"Which suppliers have non-standard payment terms
# MAGIC (Net > 60 days) AND annual spend > EUR 1,000,000?"* is now pure SQL over `contracts_extracted` —
# MAGIC fields `ai_extract` lifted from the contract PDFs. Returns **exactly Tronox + Allnex**. That is the
# MAGIC payoff: one `ai_parse_document` output feeds both a vector index for semantic Q&A and a typed table
# MAGIC for analytical SQL.

# COMMAND ----------

display(spark.sql(f"""
SELECT supplier, category, annual_spend_eur, payment_terms_days, termination_notice_days
FROM {DOCS}.contracts_extracted
WHERE payment_terms_days > 60 AND annual_spend_eur > 1000000
ORDER BY annual_spend_eur DESC"""))
# Expect exactly two rows — Tronox and Allnex.

# COMMAND ----------

# MAGIC %md
# MAGIC ## What we proved
# MAGIC
# MAGIC | Step | Result |
# MAGIC |---|---|
# MAGIC | **Parse** | `ai_parse_document` — native, no fallback. 14/14 PDFs. |
# MAGIC | **Classify** | `ai_classify` — native. 14/14 correct vs folder. |
# MAGIC | **Extract** | `ai_extract` — native. SDS + contract fields typed; `non_standard_flag` in SQL. |
# MAGIC | **Embed** | `databricks-qwen3-embedding-0-6b` via `ai_query`, 1024-dim, CDF on. |
# MAGIC | **Vector Search** | delta-sync index `chunks_idx` (self-managed embeddings) → READY. |
# MAGIC | **Search + RAG** | "TiO2 storage and PPE" → TiO2 SDS chunks top-ranked → grounded, cited answer. |
# MAGIC | **Fusion** | SQL over extracted contracts → exactly Tronox + Allnex. |
# MAGIC
# MAGIC The entire parse → classify → extract path ran on **native `ai_*` functions** with no chat-model
# MAGIC fallback. The same parsed source answers both a semantic question and an analytical one — unstructured
# MAGIC and structured intelligence from one governed catalog.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **That completes the five chapters.** From a governed supervisor that *answers* (CH1), to agents that
# MAGIC *act* on a governed write plane (CH2), to an *autonomous* loop bounded by policy (CH3), to *trust +
# MAGIC governance* at scale (CH4), to *document intelligence* over raw PDFs (CH5) — every step governed and
# MAGIC traceable end to end.
