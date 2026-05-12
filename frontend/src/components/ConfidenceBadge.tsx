import clsx from "clsx";

interface Props {
  confidence: number;
  showPercent?: boolean;
}

export function confidenceLabel(c: number): string {
  if (c >= 0.95) return "Exact";
  if (c >= 0.85) return "High";
  if (c >= 0.70) return "Medium";
  if (c >= 0.50) return "Low";
  if (c > 0) return "Poor";
  return "None";
}

export function confidenceColor(c: number) {
  if (c >= 0.95) return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
  if (c >= 0.85) return "text-green-400 bg-green-400/10 border-green-400/30";
  if (c >= 0.70) return "text-amber-400 bg-amber-400/10 border-amber-400/30";
  if (c >= 0.50) return "text-orange-400 bg-orange-400/10 border-orange-400/30";
  return "text-red-400 bg-red-400/10 border-red-400/30";
}

export function ConfidenceBadge({ confidence, showPercent = false }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-mono font-medium",
        confidenceColor(confidence)
      )}
    >
      {confidenceLabel(confidence)}
      {showPercent && <span className="opacity-70">{Math.round(confidence * 100)}%</span>}
    </span>
  );
}
