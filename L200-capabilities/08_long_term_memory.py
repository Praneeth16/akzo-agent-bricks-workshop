# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC Long-term memory is a **pgvector** table on Lakebase: we store each memory's text plus its embedding, and
# MAGIC retrieve by semantic similarity. We need `psycopg` (the Postgres driver) and a recent `databricks-sdk`
# MAGIC (for the Lakebase credential + the embedding/chat serving calls). Run this cell first, then restart Python.

# COMMAND ----------

# MAGIC %pip install -qq "psycopg[binary]" "databricks-sdk>=0.96"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 8 — Durable, cross-session memory (semantic long-term memory on Lakebase)
# MAGIC
# MAGIC ### Where this sits in the workshop
# MAGIC
# MAGIC L100 chapter 3 gave an agent **short-term** memory: a thread of turns in Lakebase, so a conversation
# MAGIC remembers what was said *a moment ago*. Chapters 1–7 here built agents that route, act, self-govern, and
# MAGIC serve. But every one of them starts each session **cold** — open a new thread and the agent has forgotten
# MAGIC who you are, what you care about, and what you were chasing last week.
# MAGIC
# MAGIC ```
# MAGIC   short-term memory (L100 ch3)            long-term memory (HERE)
# MAGIC   ┌───────────────────────────┐          ┌────────────────────────────────────────┐
# MAGIC   │ one thread of turns        │          │ durable facts about the USER             │
# MAGIC   │ "what did we just say?"    │   +      │ "who are they, what do they care about?" │
# MAGIC   │ minutes → hours            │          │ survives across threads, days → months   │
# MAGIC   │ keyed by thread_id         │          │ keyed by user_id, retrieved by MEANING   │
# MAGIC   └───────────────────────────┘          └────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### What you build in this chapter
# MAGIC
# MAGIC A **semantic long-term memory** for the coatings copilot, backed by Lakebase Postgres + `pgvector`:
# MAGIC
# MAGIC ```
# MAGIC   PART A                  PART B                   PART C                    PART D
# MAGIC   ┌──────────┐            ┌──────────────┐         ┌──────────────────┐      ┌──────────────────┐
# MAGIC   │ embed +  │            │ semantic     │         │ LLM-managed      │      │ the copilot that │
# MAGIC   │ store a  │  ───────▶  │ recall       │ ──────▶ │ memory: save /   │ ───▶ │ remembers YOU    │
# MAGIC   │ memory   │  pgvector  │ by meaning   │  tools  │ search / delete  │ wire │ across sessions  │
# MAGIC   └──────────┘            └──────────────┘         └──────────────────┘      └──────────────────┘
# MAGIC    text → vector          cosine top-k             the agent decides          per-user, governed
# MAGIC ```
# MAGIC
# MAGIC ### The 3-beat rhythm (every part)
# MAGIC 1. **SEE** — the memory behaviour the part is built on.
# MAGIC 2. **TWEAK** — change one thing (a memory, the query, what the agent saves) and re-run.
# MAGIC 3. **RETURN** — see how that part becomes a piece of a copilot that remembers the user.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - A **Lakebase** database instance (Compute → Database instances). Same one L100 ch3 / L200 ch2–3 use.
# MAGIC - Access to a **chat** model endpoint and an **embedding** endpoint (e.g. `databricks-gte-large-en`).
# MAGIC - Permission to `CREATE EXTENSION` / `CREATE TABLE` on the Lakebase `public` schema (you, as the caller).
# MAGIC
# MAGIC ### How to run (~20 min)
# MAGIC Top-to-bottom. Set the widgets to point this at your own Lakebase instance + serving endpoints (the
# MAGIC defaults assume `databricks-claude-sonnet-4-5` / `databricks-gte-large-en` exist and auto-pick the first
# MAGIC AVAILABLE Lakebase instance — override them if your workspace differs). Watch the printed similarity
# MAGIC scores — that is the memory recalling by **meaning**, not keywords.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters
# MAGIC
# MAGIC Widgets keep the notebook portable. Leave `lakebase_instance` blank to auto-pick the first AVAILABLE
# MAGIC instance. `user_id` is whose memory we read/write — the namespace key that keeps one user's memories from
# MAGIC leaking into another's. We default it to **you** so the notebook runs end-to-end.

# COMMAND ----------

import re, uuid, json
import psycopg
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-5", "Chat model endpoint")
dbutils.widgets.text("embedding_endpoint", "databricks-gte-large-en", "Embedding model endpoint")
dbutils.widgets.text("lakebase_instance", "", "Lakebase instance name (blank = auto-pick AVAILABLE)")
dbutils.widgets.text("database", "databricks_postgres", "Postgres database")
dbutils.widgets.text("user_id", "", "User whose memory we manage (blank = current user)")

LLM_ENDPOINT = dbutils.widgets.get("llm_endpoint")
EMBEDDING_ENDPOINT = dbutils.widgets.get("embedding_endpoint")
LAKEBASE_INSTANCE = dbutils.widgets.get("lakebase_instance").strip()
DATABASE = dbutils.widgets.get("database")

w = WorkspaceClient()
USER_ID = dbutils.widgets.get("user_id").strip() or w.current_user.me().user_name

if not LAKEBASE_INSTANCE:
    available = [i for i in w.database.list_database_instances() if i.state and i.state.value == "AVAILABLE"]
    if not available:
        raise RuntimeError("No AVAILABLE Lakebase instance found. Create one or set the lakebase_instance widget.")
    LAKEBASE_INSTANCE = available[0].name
    print(f"Auto-selected Lakebase instance: {LAKEBASE_INSTANCE}")

for name, val in [("llm_endpoint", LLM_ENDPOINT), ("embedding_endpoint", EMBEDDING_ENDPOINT),
                  ("lakebase_instance", LAKEBASE_INSTANCE), ("database", DATABASE)]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", val):
        raise ValueError(f"Unsafe {name}: {val!r}.")

print("Chat model    :", LLM_ENDPOINT)
print("Embedding     :", EMBEDDING_ENDPOINT)
print("Lakebase      :", LAKEBASE_INSTANCE)
print("Memory user_id:", USER_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — connect to Lakebase and define the two model calls
# MAGIC
# MAGIC We connect to Lakebase exactly as L100 ch3 did: ask the SDK for a short-lived **database credential** and
# MAGIC open a `psycopg` connection over TLS, authenticated as **you** (so Postgres permissions apply). Then two
# MAGIC helpers wrap the serving endpoints: `embed()` turns text into vectors (long-term memory's index), and
# MAGIC `chat()` is the one chat-model call the agent reuses.

# COMMAND ----------

# --- Lakebase connection (same OAuth pattern as L100 ch3) ---
_inst = w.database.get_database_instance(name=LAKEBASE_INSTANCE)
_cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[LAKEBASE_INSTANCE])
PG_USER = w.current_user.me().user_name

conn = psycopg.connect(
    host=_inst.read_write_dns, port=5432, dbname=DATABASE, user=PG_USER,
    password=_cred.token, sslmode="require", autocommit=True,
)
print(f"Connected to Lakebase {LAKEBASE_INSTANCE} as {PG_USER}")

# --- the two model calls, via the serving REST API (works off-cluster and in jobs) ---
_host = w.config.host.rstrip("/")
_token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
import requests

def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings with the embedding endpoint. Returns one vector per input."""
    resp = requests.post(
        f"{_host}/serving-endpoints/{EMBEDDING_ENDPOINT}/invocations",
        headers={"Authorization": f"Bearer {_token}", "Content-Type": "application/json"},
        json={"input": texts}, timeout=60,
    )
    resp.raise_for_status()
    return [row["embedding"] for row in resp.json()["data"]]

def chat(messages: list[dict], tools: list | None = None) -> dict:
    """One chat-model call everything reuses. Returns the assistant *message* (so callers can read either
    .content for text, or .tool_calls when tools are passed). Pass `tools` to let the model call them."""
    payload = {"messages": messages, "temperature": 0.1}
    if tools:
        payload["tools"] = tools
    resp = requests.post(
        f"{_host}/serving-endpoints/{LLM_ENDPOINT}/invocations",
        headers={"Authorization": f"Bearer {_token}", "Content-Type": "application/json"},
        json=payload, timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]

EMBED_DIM = len(embed(["dimension probe"])[0])
print("Embedding dimension:", EMBED_DIM)

# COMMAND ----------

# MAGIC %md
# MAGIC # PART A — Store a memory (text → vector → Lakebase)
# MAGIC
# MAGIC A long-term memory is one row: a **user_id**, a short **memory_key**, the **content** (what to remember),
# MAGIC and its **embedding** (the content as a vector, so we can search by meaning later). `pgvector` adds the
# MAGIC `VECTOR` column type and the `<=>` cosine-distance operator to Postgres — no external vector database.

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — create the memory store
# MAGIC
# MAGIC We enable the `vector` extension and create one table. The `VECTOR(EMBED_DIM)` column holds the embedding;
# MAGIC `UNIQUE (user_id, memory_key)` makes writes an **upsert** (re-saving a key updates it, not duplicates it).
# MAGIC The table is keyed by `user_id` — that is the namespace that keeps each user's memories private.

# COMMAND ----------

with conn.cursor() as cur:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS akzo_agent_ltm (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    TEXT          NOT NULL,
            memory_key TEXT          NOT NULL,
            content    TEXT          NOT NULL,
            embedding  VECTOR({EMBED_DIM}) NOT NULL,
            created_at TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ   NOT NULL DEFAULT now(),
            UNIQUE (user_id, memory_key)
        )
    """)
    # Guard: if the table already exists from a run with a different embedding endpoint, its vector
    # dimension will not match EMBED_DIM and every insert/search would fail with a cryptic error. Catch
    # it here with a clear message instead. pgvector stores the dimension directly in atttypmod.
    cur.execute("""
        SELECT a.atttypmod
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = 'akzo_agent_ltm' AND a.attname = 'embedding'
    """)
    existing_dim = cur.fetchone()[0]
    if existing_dim != EMBED_DIM:
        raise ValueError(
            f"akzo_agent_ltm already exists with VECTOR({existing_dim}) but this embedding endpoint "
            f"produces {EMBED_DIM}-dim vectors. Either switch back to the original embedding_endpoint, "
            f"or DROP TABLE akzo_agent_ltm and re-run to rebuild the store at the new dimension."
        )
print(f"Table akzo_agent_ltm is ready (VECTOR({EMBED_DIM}); one row = one durable memory about a user).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The save primitive
# MAGIC
# MAGIC `save_memory` embeds the content and upserts the row. This is the only write path — both the manual demo
# MAGIC below and the LLM-managed tool in Part C go through it, so there is exactly one place memory is written.

# COMMAND ----------

def save_memory(user_id: str, memory_key: str, content: str) -> str:
    """Embed `content` and upsert one memory row for a user. Returns a status string."""
    vec = embed([content])[0]
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO akzo_agent_ltm (user_id, memory_key, content, embedding)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id, memory_key)
               DO UPDATE SET content = EXCLUDED.content,
                             embedding = EXCLUDED.embedding,
                             updated_at = now()""",
            (user_id, memory_key, content, str(vec)),
        )
    return f"saved '{memory_key}'"

# Seed three durable facts about the EMEA controller persona from the workshop story.
SEED = {
    "role_and_focus":  "User is the AkzoNobel EMEA finance controller; their priority is Decorative Paints EMEA gross margin.",
    "report_style":    "User wants answers as a one-line headline, then a four-way bridge (price / volume / FX / cost).",
    "open_investigation": "User is tracking the Q2 2026 margin drop and the Rotterdam-NL to EMEA-DACH lane OTIF recovery.",
}
for k, v in SEED.items():
    print(save_memory(USER_ID, k, v))

# COMMAND ----------

# MAGIC %md
# MAGIC # PART B — Recall by meaning (semantic search)
# MAGIC
# MAGIC The point of long-term memory is recall by **meaning**, not exact keys. We embed the *query* and order
# MAGIC memories by cosine distance (`<=>`). A question that shares no words with a memory still finds it, as long
# MAGIC as it is about the same thing.

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — search returns the most relevant memories
# MAGIC
# MAGIC `search_memory` embeds the query and returns the top-k by similarity (`1 - cosine_distance`, so 1.0 =
# MAGIC identical meaning). Note the query below shares almost no words with the stored facts — recall is semantic.

# COMMAND ----------

def search_memory(user_id: str, query: str, limit: int = 3) -> list[dict]:
    """Return a user's memories most semantically similar to `query`, most-similar first."""
    qvec = embed([query])[0]
    with conn.cursor() as cur:
        cur.execute(
            """SELECT memory_key, content, 1 - (embedding <=> %s::vector) AS similarity
               FROM akzo_agent_ltm
               WHERE user_id = %s
               ORDER BY embedding <=> %s::vector
               LIMIT %s""",
            (str(qvec), user_id, str(qvec), limit),
        )
        return [{"memory_key": k, "content": c, "similarity": round(float(s), 3)} for k, c, s in cur.fetchall()]

import pandas as pd
hits = search_memory(USER_ID, "How should I format this person's margin analysis, and what are they working on?")
display(pd.DataFrame(hits))
# Expect all three seeds to score similarly (~0.5+) — they are all about the same controller — ordered by
# semantic relevance to the query. The next cell shows a sharper case where one memory clearly wins.

# COMMAND ----------

# MAGIC %md
# MAGIC **What to look for:** the `similarity` column orders the memories by **meaning**, even though the query
# MAGIC never said "bridge" or "Rotterdam". With three facts about one controller the scores cluster (they are all
# MAGIC about this user); the `fx_sensitivity` tweak next is the clean case where one memory clearly wins. That
# MAGIC semantic recall is what makes long-term memory useful — the agent does not need the exact words back.

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — add a memory, watch recall shift
# MAGIC
# MAGIC Save one more fact, then re-run a query it should now win. New memory, no schema change, no reindex — the
# MAGIC embedding goes straight into the same table and is immediately searchable.

# COMMAND ----------

save_memory(USER_ID, "fx_sensitivity", "User always asks about the USD/EUR FX effect on raw-material cost when margin moves.")
hits = search_memory(USER_ID, "Does the currency move matter for the cost story?")
display(pd.DataFrame(hits))
# Expect the new fx_sensitivity memory to rank #1 — it is the closest in meaning to an FX/currency question.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART C — LLM-managed memory (the agent decides what to remember)
# MAGIC
# MAGIC So far *we* called save/search. In a real copilot the **agent** decides: it recalls relevant memories at
# MAGIC the start of a turn, and saves durable new facts the user reveals. We expose three tools and let the model
# MAGIC choose when to use them — the same pattern a managed store (DatabricksStore) drives for you.

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — the three memory tools
# MAGIC
# MAGIC `save` and `search` reuse the primitives from Parts A/B; `delete` is new and matters for governance (a user
# MAGIC can have a fact forgotten). These are plain Python functions the agent calls — no framework required.

# COMMAND ----------

def delete_memory(user_id: str, memory_key: str) -> str:
    """Forget one memory. The compliance primitive: a user can ask the agent to delete what it knows."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM akzo_agent_ltm WHERE user_id = %s AND memory_key = %s", (user_id, memory_key))
        return f"deleted '{memory_key}'" if cur.rowcount else f"no memory '{memory_key}' to delete"

# The tool schema the chat model sees. user_id is injected by us at call time (NOT chosen by the model),
# so the agent can never read or write another user's memories.
MEMORY_TOOLS = [
    {"type": "function", "function": {
        "name": "search_memory",
        "description": "Recall durable facts about the current user from long-term memory. Call this FIRST on any "
                       "question that depends on who the user is, what they prefer, or what they are working on.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What you want to recall about the user."}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "save_memory",
        "description": "Save a durable NEW fact the user revealed about themselves, their role, preferences, or "
                       "ongoing work. Do NOT save one-off question content.",
        "parameters": {"type": "object", "properties": {
            "memory_key": {"type": "string", "description": "Short snake_case key, e.g. preferred_region."},
            "content": {"type": "string", "description": "The fact to remember, as a full sentence."}},
            "required": ["memory_key", "content"]}}},
    {"type": "function", "function": {
        "name": "delete_memory",
        "description": "Forget a specific memory when the user asks you to.",
        "parameters": {"type": "object", "properties": {
            "memory_key": {"type": "string", "description": "The key of the memory to delete."}}, "required": ["memory_key"]}}},
]

_TOOL_IMPL = {  # user_id is bound here, never taken from the model's arguments
    "search_memory": lambda args: json.dumps(search_memory(USER_ID, args["query"])),
    "save_memory":   lambda args: save_memory(USER_ID, args["memory_key"], args["content"]),
    "delete_memory": lambda args: delete_memory(USER_ID, args["memory_key"]),
}
print("Memory tools ready:", [t["function"]["name"] for t in MEMORY_TOOLS])

# COMMAND ----------

# MAGIC %md
# MAGIC ## The memory-aware agent loop
# MAGIC
# MAGIC `memory_agent` runs a small tool-calling loop: send the question + tools, run any tool the model calls
# MAGIC (binding `user_id` ourselves), feed results back, repeat until the model answers. This is the same
# MAGIC route→run→observe loop as the supervisor (ch1), here over memory tools instead of domain legs.

# COMMAND ----------

MEMORY_SYSTEM = (
    "You are the AkzoNobel coatings copilot with long-term memory about the current user. "
    "At the start of a turn, call search_memory to recall who they are and what they care about, and tailor "
    "your answer to it. When the user reveals a durable fact about themselves, call save_memory. "
    "Honour delete requests with delete_memory. Be concise."
)

def memory_agent(user_msg: str, max_steps: int = 5, verbose: bool = True) -> str:
    """A tool-calling agent with long-term memory. Returns the final assistant answer."""
    messages = [{"role": "system", "content": MEMORY_SYSTEM}, {"role": "user", "content": user_msg}]
    for _ in range(max_steps):
        msg = chat(messages, tools=MEMORY_TOOLS)   # the one shared chat call, now with memory tools
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return msg.get("content") or "(no content)"
        for tc in tool_calls:
            name = tc["function"]["name"]
            # Be defensive: a model can emit an unknown tool or malformed JSON args. Feed the error
            # back as the tool result so the agent can recover, rather than crashing the notebook.
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
                if name not in _TOOL_IMPL:
                    raise KeyError(name)
                result = _TOOL_IMPL[name](args)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                result = f"tool error: {type(e).__name__}: {e}"
            if verbose:
                print(f"  [tool] {name}({tc['function']['arguments']}) -> {str(result)[:90]}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
    return "(stopped: hit max tool steps)"

# COMMAND ----------

# MAGIC %md
# MAGIC ## SEE — the agent recalls the user without being told
# MAGIC
# MAGIC Ask a vague question that only makes sense if the agent knows the user. Watch the trace: it calls
# MAGIC `search_memory`, recalls the controller's role + report style, and tailors the answer — no context pasted in.

# COMMAND ----------

print(memory_agent("Give me the headline on where my numbers stand and how you'd lay it out for me."))
# Expect: a [tool] search_memory line, then an answer in the user's preferred headline + four-way-bridge format,
# referencing Decorative Paints EMEA margin — recalled from memory, not stated in the question.

# COMMAND ----------

# MAGIC %md
# MAGIC ## TWEAK — teach it a new fact, prove it persisted
# MAGIC
# MAGIC Tell the agent something durable about yourself; it should call `save_memory`. Then read the raw table to
# MAGIC confirm the row is really in Lakebase — this is the memory that will survive into the next session.

# COMMAND ----------

print(memory_agent("From now on, also flag any account churn risk in EMEA whenever you brief me on margin."))
print("\n--- memories now stored for this user ---")
with conn.cursor() as cur:
    cur.execute("SELECT memory_key, content, updated_at FROM akzo_agent_ltm WHERE user_id = %s ORDER BY updated_at DESC", (USER_ID,))
    display(pd.DataFrame(cur.fetchall(), columns=["memory_key", "content", "updated_at"]))
# Expect a new memory row (e.g. briefing_preference about EMEA churn) saved by the agent.

# COMMAND ----------

# MAGIC %md
# MAGIC # PART D — RETURN: the copilot that remembers you across sessions
# MAGIC
# MAGIC The payoff: a **brand-new session** (no chat history) still knows the user, because memory lives in
# MAGIC Lakebase keyed by `user_id`, not in the thread. We simulate "next week" by calling the agent fresh — the
# MAGIC short-term thread is empty, yet the long-term memory carries the user forward.

# COMMAND ----------

# A fresh session: brand-new conversation, nothing in the message history but the question.
print(memory_agent("Morning — what should I be looking at today, and remember how I like it framed."))
# Expect: search_memory recalls role + report_style + open_investigation + the churn-briefing preference you just
# taught, and the answer reflects all of it — across a session boundary, with zero pasted context.

# COMMAND ----------

# MAGIC %md
# MAGIC ## RETURN — short-term + long-term, the two halves of agent memory
# MAGIC
# MAGIC | | Short-term (L100 ch3) | Long-term (this chapter) |
# MAGIC |---|---|---|
# MAGIC | **Question it answers** | "what did we just say?" | "who is this user, what do they care about?" |
# MAGIC | **Keyed by** | `thread_id` | `user_id` |
# MAGIC | **Retrieved by** | turn order | semantic similarity (pgvector `<=>`) |
# MAGIC | **Lifespan** | minutes → hours | days → months, across sessions |
# MAGIC | **Storage** | Lakebase table of turns | Lakebase table of embedded facts |
# MAGIC
# MAGIC A production copilot uses **both**: the checkpointer for the live conversation, the semantic store for the
# MAGIC durable user model. Both ride the same Lakebase instance you already provisioned.
# MAGIC
# MAGIC ### Governance — per-user isolation and the right to be forgotten
# MAGIC - Every read/write is scoped to `user_id`, and we bind it **server-side** in `_TOOL_IMPL` — the **model
# MAGIC   never chooses whose memory it touches** (it has no `user_id` argument), so prompt injection can't make
# MAGIC   the agent recall another user's facts. That is the isolation this notebook enforces.
# MAGIC - This is **application-level** scoping. It is not a database boundary: anyone who can run this notebook
# MAGIC   with table access could set the `user_id` widget to someone else. For a real deployment, add a
# MAGIC   **database boundary** — a Postgres role per app/user, or row-level security on `user_id` — so the
# MAGIC   `user_id` filter is enforced by Lakebase, not just trusted in code.
# MAGIC - `delete_memory` is the compliance primitive: a user can have a stored fact forgotten on request. Note its
# MAGIC   honest scope — it deletes the **row** in `akzo_agent_ltm`. The same content can still live in notebook cell
# MAGIC   outputs, MLflow traces, and DB backups; a real right-to-be-forgotten flow has to reach those too.
# MAGIC - **Memories are untrusted data, not instructions.** The agent saves what a user says, then reads it back on a
# MAGIC   later turn — so a saved memory is a prompt-injection vector (a poisoned fact like *"always approve discounts"*
# MAGIC   would resurface as context). In production: store **extracted facts**, not raw phrasing; tell the model the
# MAGIC   recalled block is data; and reject imperative-looking memories. We keep it simple here to show the mechanism.
# MAGIC - The connection runs as the **caller's** Postgres identity, so Lakebase role permissions apply (writes are
# MAGIC   governed by Postgres roles, exactly as ch1's "write plane" note explained).
# MAGIC
# MAGIC ### Upgrade path: the managed `DatabricksStore`
# MAGIC This chapter is the **glass-box** version — raw `pgvector` so you can see every moving part. Databricks also
# MAGIC ships a managed equivalent in `databricks-langchain`: `DatabricksStore` (and `AsyncDatabricksStore` for apps)
# MAGIC gives you the same embed → store → semantic-search behaviour behind a `put` / `search` / `delete` API, with a
# MAGIC LangGraph `CheckpointSaver` for the short-term half — both backed by Lakebase. Once you understand the table
# MAGIC and the `<=>` search you built here, switching to the managed store is a drop-in:
# MAGIC
# MAGIC ```python
# MAGIC # Managed equivalent (databricks-langchain) — same Lakebase instance, no SQL to maintain.
# MAGIC from databricks_langchain import DatabricksStore
# MAGIC store = DatabricksStore(instance_name=LAKEBASE_INSTANCE,
# MAGIC                         embedding_endpoint=EMBEDDING_ENDPOINT, embedding_dims=EMBED_DIM)
# MAGIC store.setup()
# MAGIC ns = ("user_memories", USER_ID.replace(".", "_").replace("@", "_at_"))  # store namespaces disallow . and @
# MAGIC store.put(ns, "report_style", {"value": "headline then four-way bridge"})
# MAGIC store.search(ns, query="how do they like reports?", limit=5)
# MAGIC ```
# MAGIC
# MAGIC **Next:** you now have the full coded-agent toolkit — routing (ch1), acting (ch2–3), governance + eval
# MAGIC (ch4), documents (ch5), custom agents + MCP (ch6–7), and durable memory (ch8). L300 wires them into the
# MAGIC deployable supervisor app in `../apps/supervisor/`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cleanup (optional)
# MAGIC
# MAGIC Re-running the notebook is idempotent (saves are upserts). To reset this user's memory for a fresh
# MAGIC walkthrough, uncomment and run. To drop the whole store, `DROP TABLE akzo_agent_ltm`.

# COMMAND ----------

# with conn.cursor() as cur:
#     cur.execute("DELETE FROM akzo_agent_ltm WHERE user_id = %s", (USER_ID,))
#     print("Cleared memories for", USER_ID)
conn.close()
print("Lakebase connection closed.")
