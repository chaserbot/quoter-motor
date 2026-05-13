import clsx from "clsx";

const STEPS = [
  "Source Quote",
  "Review Matches",
  "New Quote Details",
  "Diff + Validation",
  "Push to Flex",
];

interface Props {
  current: number; // 0-indexed
}

export function StepNav({ current }: Props) {
  return (
    <div className="flex items-center gap-0 mb-8 overflow-x-auto pb-2">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center shrink-0">
          <div className="flex flex-col items-center">
            <div
              className={clsx(
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-bold border-2 transition-colors",
                i < current
                  ? "bg-emerald-600 border-emerald-600 text-white"
                  : i === current
                  ? "bg-sky-600 border-sky-600 text-white"
                  : "bg-transparent border-surface-border text-slate-600"
              )}
            >
              {i < current ? "✓" : i + 1}
            </div>
            <span
              className={clsx(
                "text-xs mt-1 whitespace-nowrap",
                i === current
                  ? "text-sky-400"
                  : i < current
                  ? "text-emerald-500"
                  : "text-slate-600"
              )}
            >
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={clsx(
                "h-px w-12 mx-1 mb-4",
                i < current ? "bg-emerald-600" : "bg-surface-border"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
