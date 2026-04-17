export const pct = (value: number): string => {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
};

export const num2 = (value: number): string => {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(2);
};

export const signedPct = (delta: number): string => {
  const p = (delta * 100).toFixed(1);
  if (delta > 0) return `+${p}%`;
  return `${p}%`;
};

export const shortDoi = (doi: string, max = 28): string => {
  if (doi.length <= max) return doi;
  return `${doi.slice(0, 10)}…${doi.slice(-14)}`;
};

export const truncate = (s: string | null | undefined, n: number): string => {
  if (!s) return "";
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
};

export const formatTimestamp = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};
