# Starter Prompt: Reusable AgentOps Factory

Paste this into Databricks Genie code or your ai-dev-kit coding assistant.

```text
We are a hackathon team building Track 20: Reusable AgentOps Factory on Databricks Free Edition (or in Vocareum, if that is your assigned lab environment).

Use these values:
- catalog: <TEAM_CATALOG>
- warehouse: <WAREHOUSE_ID_OR_NAME>
- workspace_url: <WORKSPACE_URL>
- track_readme: hackathon-starter-kit/tracks/20-agentops-factory/README.md
- worked_example_track: <WORKED_EXAMPLE_TRACK>

This is not a new agent; do not create a new Genie space or Knowledge
Assistant. This track operates on the artifacts another already-built
track has produced.

Read the README and eval set for <WORKED_EXAMPLE_TRACK> (pick a track
from this hackathon that already has a working demo). From it, produce:
1. a standard eval-set schema (question, expected answer/behavior,
   source citation, judge type) that <WORKED_EXAMPLE_TRACK>'s eval set
   can be mapped onto
2. a naming convention for agents, Genie spaces, and tables (for
   example, akzo_<domain>_<pattern>), applied as a check against
   <WORKED_EXAMPLE_TRACK>'s actual agent/space/table names
3. a promotion checklist: the minimum bar an agent must clear (eval set
   present, groundedness judge passing, governance note present, demo
   script runnable) before it is considered "promotable" beyond
   hackathon-demo status
4. the gaps found when applying all three to <WORKED_EXAMPLE_TRACK>

Governance requirements:
- the promotion checklist must require a governance note (citations,
  approval gates, or masking) as a promotion criterion, not an optional extra
- if <WORKED_EXAMPLE_TRACK> cannot be cleanly mapped onto the standard
  schema, document the mismatch rather than forcing a fit

Return the eval-set schema, naming-convention check, and promotion
checklist as reusable documents, plus a 3-minute demo script that walks
through applying them to <WORKED_EXAMPLE_TRACK>.
```
