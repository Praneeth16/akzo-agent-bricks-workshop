# Track 20: Reusable AgentOps Factory

## Use Case And Target User

- **Use case:** #20 Reusable AgentOps factory
- **Primary users:** platform engineering, AI governance leads, hackathon organizers
- **Business question:** Once one team has built a good agent, how do the other 19 tracks reach the same bar for eval sets, naming, and promotion without re-inventing it each time?
- **Success signal:** A standardized eval-set schema, naming convention, and promotion checklist exist and can be applied to any already-built track.

## Hackathon Goal

Take an already-built track from this hackathon and extract a reusable AgentOps pattern from it: a standard eval-set schema, a naming convention for agents and tables, and a promotion checklist any team can run before calling their agent "done."

## Starter Architecture

- **Agent pattern:** none — this track is a process and tooling layer, not a new agent
- **Data plane:** the eval sets and metadata of one or more already-built tracks
- **Tool plane:** eval-set schema generator, naming-convention linter, promotion checklist
- **Control plane:** the promotion checklist itself is the governance artifact this track produces

## Data And Resources

- **Inputs:** the README and eval set of one already-built track from this hackathon (pick any track that has a working demo by the time you start this one).
- **No new data is generated for this track** — it operates on the artifacts other tracks already produced.
- **Environment:** Free Edition ships Genie, Genie Code, and Agent Bricks natively — no Vocareum needed. Follow `../../../SETUP.md` steps 1-4 to provision.

**Positioning note:** this track works best introduced on Day 2 of the hackathon, once at least one other track has a working agent and eval set to extract a pattern from. Introducing it on Day 1, before any agent exists, leaves nothing concrete to standardize.

## Agent Bricks Build Path

1. Pick one already-built track and read its README and eval set.
2. Define a standard eval-set schema (question, expected answer/behavior, source citation, judge type) that the chosen track's eval set can be mapped onto.
3. Define a naming convention for agents, Genie spaces, and tables (for example, `akzo_<domain>_<pattern>`) and check the chosen track against it.
4. Write a promotion checklist: the minimum bar an agent must clear (eval set present, groundedness judge passing, governance note present, demo script runnable) before it is considered "promotable" beyond hackathon-demo status.
5. Apply the schema, naming convention, and checklist to the chosen track and note any gaps found.

## MCP, Tools, And Action Hooks

- **MCP tools:** none required — this track produces documents and checklists, not a runtime agent.
- **SQL AI Functions:** none required.
- **Action-plane hooks:** none.
- **Approval model:** the promotion checklist itself is the approval gate other tracks will be measured against.

## Evaluation And Governance

- **Eval set:** not applicable in the usual sense — this track's "eval" is whether its schema and checklist can be successfully applied to a real track without major rework.
- **Judges:** peer review from the team whose track was used as the worked example.
- **Governance:** the promotion checklist should explicitly require a governance note (citations, approval gates, or masking) as a promotion criterion, not an optional extra.
- **Failure behavior:** if the chosen track cannot be cleanly mapped onto the standard schema, document the mismatch rather than forcing a fit.

## Demo Script

1. Introduce the worked-example track and show its current eval set and README.
2. Show the standardized eval-set schema and how the worked example maps onto it.
3. Show the naming-convention check against the worked example's agents and tables.
4. Walk through the promotion checklist item by item for the worked example.
5. Close with the gaps found and what the worked-example team would need to do to reach "promotable" status.

## Judging Rubric

| Category | Points | Track-specific evidence |
|---|---:|---|
| Business fit | 25 | Solves a real cross-team standardization problem, not a novelty |
| Agent quality | 25 | Clean, reusable schema and checklist rather than track-specific notes |
| Governance | 20 | Governance is a first-class item in the promotion checklist |
| Demo completeness | 20 | Checklist and schema shown working against a real worked example |
| Reuse | 10 | Schema and checklist genuinely applicable to any of the other 19 tracks |

## Stretch Goals

- Apply the checklist to a second track and compare results.
- Add an automated naming-convention linter script.
- Draft a lightweight promotion dashboard across all hackathon tracks.
