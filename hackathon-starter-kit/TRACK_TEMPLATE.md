# Track Template

Use this structure for every hackathon track. Keep the track focused enough that a team can reach a working demo in one day.

---

## Use Case And Target User

- **Use case:** `<rank and name — see the Track Catalog tables in ../README.md>`
- **Primary users:** `<roles>`
- **Business question:** `<the painful decision or workflow this agent improves>`
- **Success signal:** `<what gets faster, safer, or better>`

---

## Hackathon Goal

Build a working Agent Bricks demo that:

1. Answers or processes one realistic user request.
2. Uses at least one governed data source or document set.
3. Shows evidence, citations, or SQL/tool traces.
4. Includes at least one quality or governance check.
5. Ends with a clear user-facing result.

---

## Starter Architecture

Describe the minimum viable build:

- **Agent pattern:** `<Genie Space | Knowledge Assistant | Supervisor | code-your-own | document extraction | classification>`
- **Data plane:** `<tables, volumes, vector index, Genie space>`
- **Tool plane:** `<SQL AI Functions, MCP tools, UC functions, action-plane connectors>`
- **Control plane:** `<evaluation, tracing, AI Gateway, permissions, human approval>`

---

## Data And Resources

List the resources the team should use, and mark each as provided or team-built:

- **Provided tables:** `<catalog.schema.table from the shared setup>`
- **Team-built tables:** `<tables to create with generate-synthetic-data>`
- **Documents:** `<volume path or document type>`
- **Genie spaces:** `<Akzo Finance | Akzo SCM | Akzo Commercial | new space>`
- **Vector Search:** `<endpoint and index if needed>`

If a resource is not in the shared `../data/` setup, use the `generate-synthetic-data` skill to create it in your own personal schema. For team setup and the ai-dev-kit skill order, see the README's "Team Working Model" and "Genie Code Prompting Rules" sections.

---

## Agent Bricks Build Path

1. Start from the recommended workshop level.
2. Paste the matching `starter-prompts/` file into Databricks Genie code or the ai-dev-kit coding assistant.
3. Create or reuse the Agent Bricks type named in the architecture.
4. Add the track-specific instructions, examples, and guardrails.
5. Add one tool or MCP call if the agent needs external context.
6. Run the sample prompts and save traces for the demo.

---

## MCP, Tools, And Action Hooks

Define the optional extension points:

- **MCP tools:** `<read-only lookup, policy check, document retrieval, action proposal>`
- **SQL AI Functions:** `<ai_query, ai_forecast, ai_summarize, ai_extract, ai_parse_document, ai_classify, ai_mask>`
- **Action-plane hooks:** `<email, ticket, Teams, SharePoint, ERP PO, CRM>`
- **Approval model:** `<read-only | propose-only | human approval | L4 within-policy auto-approve>`

---

## Evaluation And Governance

Include the minimum quality bar:

- **Eval set:** 5-10 representative questions or documents.
- **Judges:** correctness, groundedness, extraction completeness, or policy compliance.
- **Governance:** Unity Catalog permissions, AI Gateway controls, masking, citations, and audit trail where relevant.
- **Failure behavior:** what the agent should do when data is missing, ambiguous, or out of scope.

---

## Demo Script

Use a three-minute demo:

1. Show the user request.
2. Show the agent selecting data, documents, tools, or routing.
3. Show the answer, extracted fields, action proposal, or approval queue.
4. Show one trace, eval result, citation, or audit record.
5. Close with the business impact.

---

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | `<workflow impact>`
| Agent quality | 25 | `<grounded answer, extraction quality, routing, tool use>`
| Governance | 20 | `<permissions, approvals, citations, audit>`
| Demo completeness | 20 | `<end-to-end working flow>`
| Reuse | 10 | `<uses workshop kit patterns>`

---

## Stretch Goals

- Add multi-turn memory.
- Add a second domain or document source.
- Add an action-plane connector with approval.
- Add regression evaluation before deployment.
- Add a dashboard or AppKit view for the human reviewer.

