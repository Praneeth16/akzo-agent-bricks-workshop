---
name: add-genie-space
description: Create or refine a domain Genie space for a hackathon track.
---

# add-genie-space

Use this skill when a track needs a new or refined Genie Space.

## Inputs To Ask For

- Team catalog and warehouse
- Domain: Finance, SCM, Commercial, Governance, Procurement, or custom
- Tables to ground
- Business terms the team wants Genie to understand
- Five sample questions

## Build Steps

1. Inspect the track README for the target domain and demo question.
2. Draft Genie instructions with:
   - business glossary
   - allowed tables
   - metric definitions
   - join guidance
   - out-of-scope behavior
3. Ask Databricks Genie code to produce the setup notebook or API script.
4. Add sample questions that match the team's demo path.
5. Add a quick `query_genie.py` or notebook check that asks one sample question.

## Output Shape

Return:

- Genie title and description
- Instruction block to paste or create by API
- Table grounding checklist
- Sample questions
- One verification query

## Guardrails

- Keep Genie scoped to the track domain unless the track is the multi-domain supervisor.
- Require "I do not know" behavior for missing or out-of-domain data.
- Include UC permission assumptions.

