# Track 19: Compliance And Audit Evidence Agent

## Use Case And Target User

- **Use case:** #19 Compliance and audit evidence agent
- **Primary users:** internal audit, compliance officers, control owners
- **Business question:** Does a given control have the evidence it needs to pass, according to a deterministic rule, and where is that evidence?
- **Success signal:** A control's compliance status is decided by a deterministic rule engine over structured evidence, with the LLM only summarizing and citing — never making the pass/fail judgment itself.

## Hackathon Goal

Build an audit-evidence agent that checks whether required evidence exists for a control using a deterministic rule engine (a UC function), and uses the LLM only to explain and cite the result, not to decide it.

## Starter Architecture

- **Agent pattern:** Knowledge Assistant over evidence documents plus a deterministic UC-function rule engine
- **Data plane:** evidence documents and a `controls` rules table (control id, required evidence type, rule)
- **Tool plane:** deterministic rule-check UC function, document retrieval, `ai_summarize`
- **Control plane:** the rule engine — not the LLM — decides pass/fail; the LLM explains and cites

## Data And Resources

- **Team-built documents:** synthetic audit evidence documents (control test results, sign-off records). Not in the shared setup — create with `generate-synthetic-data` and place in a UC volume.
- **Team-built tables (in your own personal schema):** a `controls` table (control id, description, required evidence type, deterministic rule). Create with `generate-synthetic-data`.
- **Genie spaces:** optional, for querying control status across the portfolio.
- **Vector Search:** new index over the generated evidence documents.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

## Agent Bricks Build Path

1. Start from `../../../L200-capabilities/06_custom_agents_and_mcp.py` for the deterministic-tool pattern.
2. Generate the `controls` table and evidence documents with `generate-synthetic-data`.
3. Write the rule engine as a deterministic UC function: given a control id, check whether the required evidence exists and matches the rule, and return pass/fail plus the evidence reference. This function must be the sole source of the pass/fail decision.
4. Build a Knowledge Assistant over the evidence documents for citation and explanation.
5. Wire the agent to call the rule-engine UC function for the decision, then use the LLM only to summarize and cite the evidence — never to override or re-derive the pass/fail call.
6. Evaluate rule-engine decision accuracy and confirm the LLM never contradicts the deterministic result.

## MCP, Tools, And Action Hooks

- **MCP tools:** control lookup, evidence-document lookup
- **SQL AI Functions:** `ai_summarize`, `ai_query`
- **Action-plane hooks:** optional audit-finding draft for a failed control
- **Approval model:** human review of any failed-control finding before it is filed

## Evaluation And Governance

- **Eval set:** 8 controls with expected pass/fail outcome and expected evidence reference.
- **Judges:** rule-engine decision correctness, citation accuracy, and a specific check that the LLM's stated outcome always matches the deterministic function's output.
- **Governance:** the compliance judgment is made only by the deterministic UC function; the LLM is never the source of a pass/fail decision.
- **Failure behavior:** return "insufficient evidence" from the rule engine when required evidence is missing, rather than letting the LLM infer compliance.

## Demo Script

1. Show the `controls` table and one control's required evidence rule.
2. Call the rule-engine UC function directly and show its deterministic pass/fail output.
3. Ask the agent the same question in natural language and show it citing the same deterministic result.
4. Show a failing control and its "insufficient evidence" reason.
5. Close by showing the audit-finding draft for the failed control.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Addresses a real audit-evidence workflow with clear risk stakes |
| Agent quality | 25 | Deterministic rule engine cleanly separated from LLM explanation |
| Governance | 20 | LLM never makes or overrides the compliance decision |
| Demo completeness | 20 | Direct rule-engine call and agent call shown to agree |
| Reuse | 10 | Rule-engine pattern reusable for any control with a checkable rule |

## Stretch Goals

- Add a full-portfolio compliance summary across all controls.
- Add a trend view of control pass rate over time.
- Add a second rule type (evidence freshness, not just existence).
