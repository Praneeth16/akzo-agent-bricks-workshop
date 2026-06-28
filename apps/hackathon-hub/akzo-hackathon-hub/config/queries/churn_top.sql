-- Top at-risk EMEA accounts in the latest month (the Commercial track narrative).
-- Runs as the app service principal.
SELECT a.account_name,
       a.segment,
       ROUND(c.churn_score, 3) AS churn_score,
       c.complaint_count,
       c.nps
FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals c
JOIN serverless_lakebase_praneeth_catalog.akzo_commercial.accounts a
  ON a.account_id = c.account_id
WHERE a.region = 'EMEA'
  AND c.month = (SELECT MAX(month) FROM serverless_lakebase_praneeth_catalog.akzo_commercial.churn_signals)
ORDER BY c.churn_score DESC
LIMIT 8
