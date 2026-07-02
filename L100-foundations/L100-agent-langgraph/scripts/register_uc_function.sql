-- Register the ONE read-only Unity Catalog function the L100 agent consumes through the
-- managed UC-functions MCP server: {host}/api/2.0/mcp/functions/{catalog}/{schema}.
--
-- Run this once in a SQL editor / notebook against your personal schema (labs that
-- restrict CREATE SCHEMA provision one flat schema per user; substitute :catalog, defaults
-- to current_catalog() if you remove the USE CATALOG line). The agent matches the MCP tool
-- by the function suffix `coatings_data_lookup`, so the catalog/schema stay portable.
--
-- This function is READ-ONLY: it uses ai_query to turn a question into a grounded answer
-- over the finance tables. It performs no writes. Unity Catalog governs EXECUTE on the
-- function and SELECT on the underlying tables, so the agent's identity is governed end to
-- end — there is no client-side SQL to police on the managed-MCP path.

-- USE CATALOG ${catalog};   -- optional; otherwise it lands in current_catalog()
USE SCHEMA <your-personal-schema>;

CREATE OR REPLACE FUNCTION coatings_data_lookup(question STRING)
RETURNS STRING
COMMENT 'Read-only lookup over AkzoNobel coatings finance data (gross margin, price, FX, cost, product performance) in your personal schema. Answers a natural-language question grounded in products and margin_actuals. No writes.'
RETURN
  SELECT ai_query(
    secret('akzo', 'llm_endpoint'),  -- or hardcode your endpoint name here, e.g. 'databricks-meta-llama-3-3-70b-instruct'
    CONCAT(
      'You are the AkzoNobel coatings finance assistant. Answer the question using ONLY ',
      'these tables: products(sku, product_name, product_line, region) and ',
      'margin_actuals(sku, region, month, units, revenue_eur, cogs_eur, gross_margin_eur). ',
      'gross_margin_pct = SUM(gross_margin_eur)/SUM(revenue_eur). Paints EMEA := ',
      'product_line=''Decorative Paints'' AND region=''EMEA''. If the data does not support ',
      'an answer, say so. Question: ', question
    )
  );

-- After registering, grant the agent's run-as principal access (replace the principal):
-- GRANT EXECUTE ON FUNCTION coatings_data_lookup TO `your-app-service-principal`;
-- GRANT SELECT ON TABLE products TO `your-app-service-principal`;
-- GRANT SELECT ON TABLE margin_actuals TO `your-app-service-principal`;
