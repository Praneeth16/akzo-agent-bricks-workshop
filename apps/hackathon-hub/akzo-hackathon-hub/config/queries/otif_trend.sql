-- Rotterdam-NL on-time-in-full % by month. Shows the May 2026 OTIF dip the SCM
-- track investigates. Runs as the app service principal.
SELECT date_format(month, 'yyyy-MM') AS month,
       ROUND(AVG(otif_pct), 1) AS otif_pct
FROM serverless_lakebase_praneeth_catalog.akzo_scm.otif
WHERE plant = 'Rotterdam-NL'
GROUP BY month
ORDER BY month
