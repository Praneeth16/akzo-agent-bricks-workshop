---
name: add-mcp-tool
description: Add one governed MCP or UC-function tool to a hackathon agent.
---

# add-mcp-tool

Use this skill when the demo needs one explicit tool call beyond a Genie or Knowledge Assistant answer.

## Inputs To Ask For

- Tool purpose
- Read-only or action-proposing
- Input schema
- Output schema
- Source table, document index, or API
- Failure behavior

## Build Steps

1. Prefer a read-only tool unless the track explicitly needs an action.
2. Define the tool schema in plain JSON-compatible fields.
3. Ask Databricks Genie code to generate:
   - the SQL or Python function
   - parameter validation
   - one happy-path test
   - one empty-result test
4. Add trace-friendly logging of tool name, inputs, and returned row count.
5. Update agent instructions to say when to call the tool.

## Output Shape

Return:

- Tool name
- Input and output schema
- Generated code or notebook cell
- Agent instruction snippet
- Verification prompt

## Guardrails

- Do not expose secrets in tool arguments.
- Mask personal or commercially sensitive fields unless needed for the demo.
- Empty results must be handled as "not found", not guessed.

