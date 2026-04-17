// OKLCH interpolation helpers for heatmap coloring.
// Red → neutral → green based on a 0..1 score.

export function heatColor(score: number, opacity = 1): string {
  const t = Math.max(0, Math.min(1, score));
  // Anchor stops (L, C, H)
  // bad: L 64 C 0.18 H 28   → red
  // mid: L 86 C 0.03 H 90   → near-neutral warm
  // ok:  L 70 C 0.13 H 145  → muted green
  let l: number, c: number, h: number;
  if (t < 0.5) {
    const u = t / 0.5;
    l = 64 + (86 - 64) * u;
    c = 0.18 + (0.03 - 0.18) * u;
    h = 28 + (90 - 28) * u;
  } else {
    const u = (t - 0.5) / 0.5;
    l = 86 + (70 - 86) * u;
    c = 0.03 + (0.13 - 0.03) * u;
    h = 90 + (145 - 90) * u;
  }
  return `oklch(${l}% ${c} ${h} / ${opacity})`;
}

export function heatTextColor(score: number): string {
  const t = Math.max(0, Math.min(1, score));
  // Dark text on the pale middle, light text on saturated ends
  if (t > 0.35 && t < 0.75) return "oklch(20% 0.02 90)";
  return "oklch(99% 0 0)";
}

// Failure-mode palette — distinct hues, same chroma/luma so stacked segments read evenly.
export const FAILURE_COLORS: Record<string, string> = {
  paywall: "oklch(55% 0.17 25)",
  login: "oklch(55% 0.15 55)",
  login_screen: "oklch(55% 0.15 55)",
  bot_check: "oklch(50% 0.18 340)",
  no_abstract: "oklch(60% 0.13 260)",
  broken_url: "oklch(55% 0.16 10)",
  non_article: "oklch(55% 0.13 200)",
  image_only: "oklch(58% 0.14 175)",
  clean: "oklch(62% 0.11 145)",
};

export function failureColor(mode: string): string {
  return FAILURE_COLORS[mode] ?? "oklch(55% 0.05 260)";
}
