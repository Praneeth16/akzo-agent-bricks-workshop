# AkzoNobel theme — shared design tokens

Brand-accurate palette, sampled from akzonobel.com (computed CSS, 2026-06-29). Used by the hub
(`hackathon-hub`, LIGHT) and the agent apps (`supervisor` etc., DARK variant). Supersedes the generic
Databricks-teal accent in `DESIGN_BRIEF.md` for brand surfaces — keep the brief's component specs
(LadderMeter, GuardrailChips, Timeline, StatusBadge) and status colors.

## Brand palette (source of truth)

| Token | Hex | RGB | Use |
|---|---|---|---|
| **AkzoNobel deep blue** | `#005192` | 0,81,146 | primary brand — buttons, headers, key fills |
| **AkzoNobel bright blue** | `#008BC5` | 0,139,197 | accent — links, focus ring, highlights, charts |
| Deep blue hover | `#003A6B` | darker | primary hover/active |
| Ink | `#333333` | text on light |
| Slate 600 / 500 / 400 | `#494949` / `#838383` / `#959595` | muted text, borders |
| Surface | `#FFFFFF` / `#FAFAFA` / `#F4F4F4` | bg / subtle / panel on light |

Status (semantic, unchanged from DESIGN_BRIEF): success `#2ecc71`, warning `#f0a500`,
error `#ff5d5d`, escalated/violet `#c678dd`. Action-plane: proposed=muted, approved=bright-blue,
executing=warning, executed=success, rejected/failed=error, escalated=violet.

## oklch (for the AppKit / Tailwind CSS vars)

LIGHT (hub):
```
--primary: oklch(0.42 0.13 252);            /* #005192 deep blue */
--primary-foreground: oklch(0.99 0 0);
--accent: oklch(0.95 0.03 240);             /* pale blue tint */
--accent-foreground: oklch(0.42 0.10 250);
--ring: oklch(0.61 0.12 236);               /* #008BC5 bright blue focus */
--chart-1: oklch(0.42 0.13 252);            /* deep blue */
--chart-2: oklch(0.61 0.12 236);            /* bright blue */
```

DARK (agent apps; bright blue leads for contrast on slate):
```
--background:#0f1117  --panel:#181b24  --panel-2:#1f2330  --border:#2a2f3d
--text:#e6e8ee  --muted:#8b90a0
--primary:#008BC5 (bright blue — primary on dark)   --primary-deep:#005192 (secondary fills)
--ring:#008BC5  --link:#4fb3e0
```

## Brand usage
- Primary CTA = deep blue `#005192` (light) / bright blue `#008BC5` (dark), white text.
- Links + focus ring = bright blue `#008BC5`.
- Headers/wordmark: "AkzoNobel" in ink `#333` with a deep-blue accent rule; keep it calm and corporate.
- One accent only — do not mix teal. Charts: deep blue + bright blue + the status hues.
- Motion 120–160ms ease-out; calm, governed-feeling, exec-credible (per DESIGN_BRIEF).
