import { useState } from "react";
import { Scorecard } from "./components/Scorecard";
import { PublisherHeatmap } from "./components/PublisherHeatmap";
import { FailureModeBar } from "./components/FailureModeBar";
import { DiffTable } from "./components/DiffTable";
import { TrendChart } from "./components/TrendChart";
import { RunSelector } from "./components/RunSelector";
import { useRuns } from "./hooks/useRuns";
import { formatTimestamp } from "./lib/format";

export default function App() {
  const { loading, error, index, currentRun, previousRun, selectRun } = useRuns();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="shell">
        <p className="empty-state">Loading runs…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shell">
        <div className="empty-state">
          <p>Could not load runs: {error}</p>
          <p className="mono" style={{ marginTop: "1em", fontSize: "var(--text-small)" }}>
            Run <code>python -m parseland_eval run --label baseline</code> in <code>eval/</code> first.
          </p>
        </div>
      </div>
    );
  }

  if (!index || index.runs.length === 0 || !currentRun) {
    return (
      <div className="shell">
        <p className="empty-state">No evaluation runs found in <code>runs/</code>.</p>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="masthead">
        <div>
          <h1>Parseland · Eval</h1>
          <p className="sub">
            A gold-standard benchmark of {currentRun.summary.overall.rows} academic DOIs
            scored against <code className="mono">parseland-lib</code>.
          </p>
        </div>
        <div className="meta">
          <RunSelector
            runs={index.runs}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              selectRun(id);
            }}
          />
          <span>v{currentRun.eval_version} · {formatTimestamp(currentRun.timestamp_utc)}</span>
          <span>
            {index.runs.length} run{index.runs.length === 1 ? "" : "s"} on disk
          </span>
        </div>
      </header>

      <Scorecard
        current={currentRun.summary.overall}
        previous={previousRun?.summary.overall ?? null}
      />

      <section>
        <div className="section-head">
          <span className="num">01 ·</span>
          <h2>Where we're losing</h2>
          <span className="dek">F1 per publisher domain · darker red → worse</span>
        </div>
        <PublisherHeatmap data={currentRun.summary.per_publisher} />
      </section>

      <section>
        <div className="section-head">
          <span className="num">02 ·</span>
          <h2>Why we're losing</h2>
          <span className="dek">Failure-mode distribution across {currentRun.summary.overall.rows} rows</span>
        </div>
        <div className="card">
          <FailureModeBar data={currentRun.summary.per_failure_mode} />
        </div>
      </section>

      <section>
        <div className="section-head">
          <span className="num">03 ·</span>
          <h2>Row-level diff</h2>
          <span className="dek">Expected · Parsed · Score — filter to drill in</span>
        </div>
        <DiffTable rows={currentRun.rows} />
      </section>

      <section>
        <div className="section-head">
          <span className="num">04 ·</span>
          <h2>Trend</h2>
          <span className="dek">Top-line metrics across every run on disk</span>
        </div>
        <div className="card">
          <TrendChart runs={index.runs} />
        </div>
      </section>

      <hr className="rule" style={{ marginTop: "var(--space-7)" }} />
      <footer
        className="mono faint"
        style={{
          padding: "var(--space-5) 0",
          fontSize: "var(--text-micro)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>parseland-eval / dashboard · reads eval/runs/*.json</span>
        <span>N = {currentRun.summary.overall.rows} · errors = {currentRun.summary.overall.errors}</span>
      </footer>
    </div>
  );
}
