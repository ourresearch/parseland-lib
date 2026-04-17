# parseland-dashboard

Static editorial dashboard for the parseland evaluation harness. Renders run artifacts produced by `../eval` — scorecard, per-publisher heatmap, failure-mode distribution, virtualized row-level diff, and trend across runs.

## Quickstart

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173
```

The dashboard reads `public/runs/*.json` which is symlinked to `../eval/runs/`. Every time you run `python -m parseland_eval run --label X`, a fresh run becomes visible on reload.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve built output locally |
| `npm run typecheck` | `tsc -b --noEmit` |

## Anti-template design direction

Editorial / data-density — not the default "card grid + gradient blob" SaaS look. Serif display (Fraunces), mono sidelines (JetBrains Mono), Inter body. OKLCH palette, `clamp()`-sized type, compositor-only motion. Respects `prefers-reduced-motion` and `prefers-color-scheme`.

## Bundle budget

Per global `rules/web/performance.md`: JS ≤ 150 KB gzipped, CSS ≤ 30 KB. Current build: ~69 KB JS, ~3 KB CSS.
