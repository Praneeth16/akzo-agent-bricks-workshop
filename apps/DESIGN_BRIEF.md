# Frontend Design Brief — AkzoNobel agent apps

Shared design language for all apps (`quote-agent`, `supervisor`, `finance-copilot`, `action-center`) + the Actions panels added to the first three. Goal: **exec-credible, calm, governed-feeling product UI — not an AI-demo toy.** Consistency across apps reads as "one platform."

## Design tokens (reuse the existing system, extended)
```
--bg:#0f1117  --panel:#181b24  --panel-2:#1f2330  --border:#2a2f3d
--text:#e6e8ee  --muted:#8b90a0
--accent:#00b39f (Databricks teal — primary actions/brand)
--accent-2:#4f8cff (links, secondary)
--warn:#f0a500  --error:#ff5d5d  --ok:#2ecc71
```
Add per-status colors for the action plane (use consistently everywhere a status appears):
```
proposed:#8b90a0(muted)  approved:#4f8cff  executing:#f0a500  executed:#2ecc71
rejected:#ff5d5d  failed:#ff5d5d  escalated:#c678dd(violet)
```
Font: system stack (already set). Sizes: H1 26 / H2 16 / body 14 / label 12. Radius 10 (cards) / 7 (controls). Spacing scale: 4/8/12/16/20/28.

## Layout
- Centered column `max-width: 1100px` (action-center may go 1280 for the queue table). Generous padding, `gap` not margins.
- Two-zone grid: primary content + a right rail (340px) for trace/explain/context. Collapses to single column < 860px.
- Header: product name + one-line subtitle (the agent's job). Small workspace/identity chip top-right.

## Components (build as small, reusable, consistent)
- **Card** — the unit of grouping. Subtle border, no heavy shadows. Optional status-tinted left border.
- **StatusBadge** — pill, status color + dot. Used in queues, detail, lineage.
- **LadderMeter** — the Action Maturity Ladder (L1 Recommend → L2 Stage & approve → L3 Execute → L4 Autonomous) as a horizontal 4-step indicator with counts; the current action's level highlighted. This is the signature exec visual — make it crisp.
- **Timeline** — vertical event lineage (action_events): dot + event + actor + ts + detail. The audit story, visible.
- **GuardrailChips** — pass/breach checks as small chips (green check / red x + reason). Makes governance tangible.
- **TracePanel** — collapsible "How this works": generated SQL (monospace, syntax-tinted), data sources, the external call + ref. Honest, not hidden.
- **Button** variants: primary (teal), ghost (border only), danger (reject). Disabled = 0.5 opacity. Loading = inline spinner, never layout shift.
- **DataTable** — for the action queue: dense, hover row highlight, sortable headers, status badge column, sticky header.

## Interaction + motion
- Optimistic where safe; always show pending/loading state; never a dead click.
- Transitions 120–160ms ease-out on hover/expand. No bouncy/gratuitous animation.
- Approve/Execute = a clear 2-step affordance (confirm intent) with the guardrail verdict shown before execute.
- Empty states have a one-line explanation + the action that fills them (e.g. "No pending actions — agents will stage them here").
- Errors inline, specific, recoverable. Never a raw stack trace in the UI.

## Anti-slop rules (enforce)
- No emoji-as-icons in the chrome; no purple-gradient hero; no fake metrics.
- Real numbers from the API only. No lorem. No centered-everything.
- Align to a grid; consistent label casing (Sentence case); consistent number/currency formatting (€ thousands separators, % to 1 dp).
- Every screen answers: what is this, what's the state, what can I do, what happened (lineage).

## The exec money-shot (action-center landing)
Top: the LadderMeter with live counts per level. Left/center: the action queue (filter by status/level/agent). Click a row → detail with GuardrailChips + Timeline + external-effect (the ref returned by email/PO/etc.) + approve/execute controls. One screen that says: **agents act, governed, audited.**

## Process
- Build with Vite + React + TS, served static by FastAPI (match existing apps' `app.yaml`).
- After building, do a self design-review pass (screenshot the running app, check against this brief: spacing rhythm, hierarchy, status-color consistency, empty/loading/error states, the ladder + timeline legibility) and fix issues before declaring done.
