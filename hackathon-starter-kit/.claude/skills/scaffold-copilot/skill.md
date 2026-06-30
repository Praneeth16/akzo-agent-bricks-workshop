---
name: scaffold-copilot
description: Create the first runnable hackathon copilot loop for a selected track in Vocareum and Databricks.
---

# scaffold-copilot

Use this skill when a team picks a track and needs the first working scaffold.

## Inputs To Ask For

- Track folder and use-case rank
- Team catalog and SQL warehouse
- Target Agent Bricks pattern: Genie Space, Knowledge Assistant, Supervisor, document extraction, classification, or code-your-own
- One demo-path question or document
- Whether the output should be a notebook, agent instructions, or app skeleton

## Build Steps

1. Read the track README and copy its demo script into the scaffold plan.
2. Create the smallest runnable loop:
   - one user request
   - one governed data source
   - one answer or structured output
   - one trace, citation, or eval checkpoint
3. Generate code with Databricks Genie code using the team's assigned catalog and warehouse.
4. Keep all table names parameterized with notebook widgets or environment variables.
5. Add a 5-row eval set before adding extra tools or UI.

## Output Shape

Return:

- Files or notebook cells to create
- Agent instructions to paste into Agent Bricks
- Sample prompts for the demo path
- Verification steps the team can run in Vocareum

## Guardrails

- Do not hardcode another team's catalog.
- Do not add mutation actions unless the track explicitly needs them.
- If data is missing, generate a preflight check instead of assuming tables exist.

