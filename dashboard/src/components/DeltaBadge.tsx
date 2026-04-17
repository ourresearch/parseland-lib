import { signedPct } from "../lib/format";

interface Props {
  current: number;
  previous: number | null;
  higherIsBetter?: boolean;
}

export function DeltaBadge({ current, previous, higherIsBetter = true }: Props) {
  if (previous === null || previous === undefined) return null;
  const delta = current - previous;
  const epsilon = 0.002;
  if (Math.abs(delta) < epsilon) {
    return <span className="delta flat">±0.0%</span>;
  }
  const goodDirection = higherIsBetter ? delta > 0 : delta < 0;
  return (
    <span className={`delta ${goodDirection ? "up" : "down"}`}>
      {goodDirection ? "▲" : "▼"} {signedPct(delta).replace(/^[+-]/, "")}
    </span>
  );
}
