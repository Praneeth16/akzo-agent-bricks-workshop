# Databricks notebook source
# MAGIC %md
# MAGIC ## Install dependencies
# MAGIC
# MAGIC Pin a recent SDK + MLflow for the serving APIs, then restart Python. (Only `%pip` in the notebook.)

# COMMAND ----------

# MAGIC %pip install --quiet "mlflow>=3.1.0" "databricks-sdk>=0.96"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC # Chapter 7 — Serve a custom / OSS / fine-tuned model
# MAGIC
# MAGIC ### Where this sits
# MAGIC
# MAGIC ```
# MAGIC   CH6  Custom agents (LangGraph) + managed MCP, served
# MAGIC   CH7  Serve a custom / OSS / fine-tuned MODEL                 <- you are here
# MAGIC ```
# MAGIC
# MAGIC CH6 served a custom *agent*. This is the model counterpart: log a model -> register to Unity Catalog
# MAGIC -> stand up a **Model Serving** endpoint, across the three routes Databricks offers.
# MAGIC
# MAGIC ```
# MAGIC   log + register (UC)  ──▶  one of three serving routes:
# MAGIC                            (a) Provisioned Throughput FM API  — supported base/fine-tuned LLMs, serverless
# MAGIC                            (b) Custom Model Serving           — any logged model (CPU, or workload_type=GPU_*)
# MAGIC                            (c) External Models via AI Gateway — third-party providers, governed (ties to CH4)
# MAGIC ```
# MAGIC
# MAGIC ### Guard-and-degrade
# MAGIC Always-run core: **log a custom pyfunc model + register to UC + in-process `predict`** (CPU, cheap, no
# MAGIC GPU). Every step that *creates a serving endpoint* is behind the `create_endpoint` flag (default
# MAGIC false) so the notebook runs green without provisioning compute. GPU / Provisioned Throughput add
# MAGIC cost + region-availability gates, so they default to walkthrough.
# MAGIC
# MAGIC ### Grounded in docs (reference)
# MAGIC - Create custom model serving endpoints (SDK, `workload_type` GPU): `.../model-serving/create-manage-serving-endpoints`
# MAGIC - Provisioned Throughput FM APIs: `.../foundation-model-apis/deploy-prov-throughput-foundation-model-apis`
# MAGIC - GPU workload types: GPU_SMALL (1xT4), GPU_MEDIUM (1xA10G), MULTIGPU_MEDIUM (4xA10G), GPU_MEDIUM_8 (8xA10G).
# MAGIC
# MAGIC ### Which route do I pick?
# MAGIC
# MAGIC | Route | Use when | Compute | Governance |
# MAGIC |---|---|---|---|
# MAGIC | (a) Provisioned Throughput FM API | the model is a Databricks-supported base/fine-tuned **FM** + you want dedicated, predictable capacity | serverless, auto-scales (no GPU mgmt) | UC-registered, billed per throughput chunk |
# MAGIC | (b) Custom Model Serving | **any** logged model (OSS, custom pyfunc, your own weights) | CPU, or `workload_type=GPU_*` | UC-registered, scale-to-zero |
# MAGIC | (c) External Models via AI Gateway | you want a **third-party** provider (OpenAI, Anthropic) governed on Databricks | none (provider hosts it) | every call logged + rate-limited by the Gateway (ties to CH4) |
# MAGIC
# MAGIC ### Prerequisites
# MAGIC Serverless; permission to register a UC model and (for the guarded steps) create serving endpoints.
# MAGIC
# MAGIC ### How to run (~15 min)
# MAGIC Top to bottom. The always-run core (log + register + in-process `predict`) is CPU-only and provisions
# MAGIC nothing. Routes (a)/(b)/(c) are walkthroughs by default; flip `create_endpoint=true` (and optionally
# MAGIC set `workload_type`) to actually stand up route (b)'s endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — parameters

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Unity Catalog (blank = current_catalog())")
dbutils.widgets.text("uc_model_name", "", "UC model name (blank = <catalog>.akzo_ops.akzo_custom_model)")
dbutils.widgets.text("serving_endpoint_name", "akzo-custom-model", "Serving endpoint name")
dbutils.widgets.dropdown("create_endpoint", "false", ["true", "false"], "Create a serving endpoint (uses compute)")
dbutils.widgets.dropdown("workload_type", "CPU", ["CPU", "GPU_SMALL", "GPU_MEDIUM"], "Workload type (GPU = cost)")

CATALOG = dbutils.widgets.get("catalog") or spark.sql("SELECT current_catalog()").first()[0]
OPS = f"{CATALOG}.akzo_ops"
UC_MODEL_NAME = dbutils.widgets.get("uc_model_name") or f"{CATALOG}.akzo_ops.akzo_custom_model"
ENDPOINT_NAME = dbutils.widgets.get("serving_endpoint_name")
CREATE_ENDPOINT = dbutils.widgets.get("create_endpoint") == "true"
WORKLOAD_TYPE = dbutils.widgets.get("workload_type")

import mlflow
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OPS}")
mlflow.set_registry_uri("databricks-uc")
print("UC model:", UC_MODEL_NAME, "| endpoint:", ENDPOINT_NAME)
print("create_endpoint:", CREATE_ENDPOINT, "| workload_type:", WORKLOAD_TYPE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log + register a custom model (always-run core)
# MAGIC
# MAGIC A tiny `mlflow.pyfunc.PythonModel` stands in for "your custom / OSS / fine-tuned model" — the
# MAGIC log -> register path is identical whatever the model is. CPU, cheap, no GPU. We register it to Unity
# MAGIC Catalog so it is governed and servable.

# COMMAND ----------

import pandas as pd
from mlflow.models import infer_signature

class AkzoCustomModel(mlflow.pyfunc.PythonModel):
    """Stand-in for a custom/OSS/fine-tuned model. Replace `predict` body with your model's inference."""
    def predict(self, context, model_input, params=None):
        # model_input: a pandas DataFrame with a 'prompt' column.
        prompts = model_input["prompt"] if isinstance(model_input, pd.DataFrame) else model_input
        return [f"[akzo-custom-model] echo: {p}" for p in list(prompts)]

example = pd.DataFrame({"prompt": ["Paints EMEA margin?"]})
model = AkzoCustomModel()
sig = infer_signature(example, model.predict(None, example))

mlflow.set_experiment(f"/Users/{w.current_user.me().user_name}/akzo_custom_model")
with mlflow.start_run():
    logged = mlflow.pyfunc.log_model(
        artifact_path="model", python_model=model,
        input_example=example, signature=sig,
        pip_requirements=["mlflow>=3.1.0", "pandas"],
    )
print("Logged:", logged.model_uri)
registered = mlflow.register_model(logged.model_uri, UC_MODEL_NAME)
print("Registered:", UC_MODEL_NAME, "version", registered.version)

# COMMAND ----------

# MAGIC %md
# MAGIC **In-process predict (always-run).** Load the registered model from UC and call it — proves the
# MAGIC log -> register -> load path before any endpoint exists.

# COMMAND ----------

loaded = mlflow.pyfunc.load_model(f"models:/{UC_MODEL_NAME}/{registered.version}")
# Expect: two "[akzo-custom-model] echo: ..." strings (the stand-in model echoes each prompt). This is the
# same inference path the serving endpoint runs, proven in-process (CPU, no auth) before any endpoint exists.
print(loaded.predict(pd.DataFrame({"prompt": ["What changed in Q2?", "Which lane broke OTIF?"]})))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Route (b) — Custom Model Serving (guarded)
# MAGIC
# MAGIC Stand up a serving endpoint for the registered model with the Workspace Client SDK. CPU by default;
# MAGIC set the `workload_type` widget to `GPU_SMALL`/`GPU_MEDIUM` for a GPU model (adds cost + availability
# MAGIC gates). Behind `create_endpoint` (default false) so verification does not provision compute.

# COMMAND ----------

from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

def build_served_entity():
    kwargs = dict(name="akzo-custom", entity_name=UC_MODEL_NAME, entity_version=registered.version,
                  workload_size="Small", scale_to_zero_enabled=True)
    if WORKLOAD_TYPE != "CPU":
        kwargs["workload_type"] = WORKLOAD_TYPE   # GPU_SMALL=1xT4, GPU_MEDIUM=1xA10G
    return ServedEntityInput(**kwargs)

if CREATE_ENDPOINT:
    w.serving_endpoints.create(
        name=ENDPOINT_NAME,
        config=EndpointCoreConfigInput(served_entities=[build_served_entity()]))
    print("Creating serving endpoint:", ENDPOINT_NAME, "(", WORKLOAD_TYPE, ") — poll the Serving UI for READY.")
else:
    print("create_endpoint=false — skipped (no compute provisioned). Would run:")
    print(f"  w.serving_endpoints.create(name='{ENDPOINT_NAME}', config=EndpointCoreConfigInput(")
    print(f"    served_entities=[ServedEntityInput(entity_name='{UC_MODEL_NAME}', entity_version='{registered.version}',")
    print(f"      workload_size='Small', workload_type='{WORKLOAD_TYPE}', scale_to_zero_enabled=True)]))")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Route (a) — Provisioned Throughput FM API (walkthrough + guarded)
# MAGIC
# MAGIC For a *supported* base or fine-tuned foundation model logged to UC, Provisioned Throughput gives
# MAGIC dedicated, auto-scaling serverless capacity (no GPU management). You check eligibility, then create
# MAGIC with `min/max_provisioned_throughput` (multiples of the model's `throughput_chunk_size`). The
# MAGIC stand-in pyfunc above is **not** an optimizable FM, so this is shown as the exact code to run against
# MAGIC a real FM, guarded so it never errors here.

# COMMAND ----------

RUN_PT = False   # set True only with a Provisioned-Throughput-eligible FM logged to UC
if RUN_PT:
    import requests
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    API_ROOT = ctx.apiUrl().get(); API_TOKEN = ctx.apiToken().get()
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    info = requests.get(
        f"{API_ROOT}/api/2.0/serving-endpoints/get-model-optimization-info/{UC_MODEL_NAME}/{registered.version}",
        headers=headers).json()
    if not info.get("optimizable"):
        print("Model is not Provisioned-Throughput eligible:", info)
    else:
        chunk = info["throughput_chunk_size"]
        requests.post(f"{API_ROOT}/api/2.0/serving-endpoints", headers=headers, json={
            "name": "akzo-pt-endpoint",
            "config": {"served_entities": [{
                "entity_name": UC_MODEL_NAME, "entity_version": registered.version,
                "min_provisioned_throughput": chunk, "max_provisioned_throughput": 2 * chunk}]}})
        print("Creating Provisioned Throughput endpoint akzo-pt-endpoint")
else:
    print("Provisioned Throughput shown as walkthrough (RUN_PT=False; the stand-in model is not an FM).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Route (c) — External Models via Unity AI Gateway (walkthrough)
# MAGIC
# MAGIC To serve a third-party provider's model under the **same governance plane as CH4**, create an
# MAGIC External Model served entity (the provider key lives in a UC secret). Every call is then governed +
# MAGIC logged by the Unity AI Gateway, exactly like the internal endpoints in CH4.
# MAGIC
# MAGIC ```python
# MAGIC from databricks.sdk.service.serving import (
# MAGIC     EndpointCoreConfigInput, ServedEntityInput, ExternalModel, OpenAiConfig)
# MAGIC w.serving_endpoints.create(
# MAGIC     name="akzo-external-openai",
# MAGIC     config=EndpointCoreConfigInput(served_entities=[ServedEntityInput(
# MAGIC         name="gpt", external_model=ExternalModel(
# MAGIC             name="gpt-4o", provider="openai", task="llm/v1/chat",
# MAGIC             openai_config=OpenAiConfig(openai_api_key="{{secrets/akzo/openai_key}}")))]))
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Consume the served model
# MAGIC
# MAGIC If an endpoint was created, query it via `ai_query`. Otherwise fall back to the in-process loaded
# MAGIC model so the cell demonstrates the same call shape.

# COMMAND ----------

if CREATE_ENDPOINT:
    try:
        out = spark.sql("SELECT ai_query(:e, :p) AS a",
                        args={"e": ENDPOINT_NAME, "p": "Summarize the Paints EMEA Q2 margin story."}).first()["a"]
        print("Endpoint response:", str(out)[:400])
    except Exception as e:
        print("Endpoint not READY yet (poll the Serving UI):", str(e)[:160])
else:
    print("(in-process) ", loaded.predict(pd.DataFrame({"prompt": ["Summarize the Paints EMEA Q2 margin story."]})))

# COMMAND ----------

# MAGIC %md
# MAGIC ## What we built
# MAGIC
# MAGIC - **Log + register (always-run)** — a custom pyfunc model to Unity Catalog, governed and servable;
# MAGIC   proven with an in-process `load_model` + `predict`.
# MAGIC - **Three serving routes** — Custom Model Serving (CPU / `workload_type=GPU_*`), Provisioned
# MAGIC   Throughput FM API (`min/max_provisioned_throughput`), and External Models via the Unity AI Gateway
# MAGIC   (governed like CH4). Endpoint creation is guarded behind `create_endpoint` so it never provisions
# MAGIC   compute during verification.
# MAGIC - **Consume** — `ai_query(endpoint, prompt)` once an endpoint is READY, or the loaded model in-process.
# MAGIC
# MAGIC Together with CH6, this is the full "bring your own agent and model, served and governed on one
# MAGIC Databricks plane" story.
