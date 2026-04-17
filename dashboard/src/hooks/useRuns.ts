import { useEffect, useState } from "react";
import { IndexSchema, RunSchema, type Index, type Run } from "../lib/schema";

interface RunsState {
  loading: boolean;
  error: string | null;
  index: Index | null;
  currentRun: Run | null;
  previousRun: Run | null;
  selectRun: (runId: string) => void;
}

export function useRuns(): RunsState {
  const [index, setIndex] = useState<Index | null>(null);
  const [currentRun, setCurrentRun] = useState<Run | null>(null);
  const [previousRun, setPreviousRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/runs/index.json", { cache: "no-store" });
        if (!res.ok) throw new Error(`index.json → ${res.status}`);
        const raw = await res.json();
        const parsed = IndexSchema.parse(raw);
        if (!cancelled) setIndex(parsed);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!index || index.runs.length === 0) return;
    const wanted = selectedId ?? index.runs[0].run_id!;
    const targetEntry = index.runs.find((r) => r.run_id === wanted) ?? index.runs[0];
    const prevEntry = index.runs.find((r, i) => i > index.runs.indexOf(targetEntry) && r.run_id);

    let cancelled = false;
    (async () => {
      try {
        const targetRes = await fetch(`/runs/${targetEntry.file}`, { cache: "no-store" });
        const targetRaw = await targetRes.json();
        const targetRun = RunSchema.parse(targetRaw);
        if (!cancelled) setCurrentRun(targetRun);

        if (prevEntry) {
          const prevRes = await fetch(`/runs/${prevEntry.file}`, { cache: "no-store" });
          const prevRaw = await prevRes.json();
          const prevRun = RunSchema.parse(prevRaw);
          if (!cancelled) setPreviousRun(prevRun);
        } else {
          if (!cancelled) setPreviousRun(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [index, selectedId]);

  return {
    loading,
    error,
    index,
    currentRun,
    previousRun,
    selectRun: setSelectedId,
  };
}
