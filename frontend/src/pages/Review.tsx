import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useQuoteStore } from "@/store/quoteStore";
import { itemName, itemQty, type FlexElement } from "@/api/client";
import { ItemMatchRow } from "@/components/ItemMatchRow";
import { StepNav } from "@/components/StepNav";

export function Review() {
  const { state, dispatch } = useQuoteStore();
  const navigate = useNavigate();

  if (!state.sourceDocument) {
    navigate("/");
    return null;
  }

  const doc = state.sourceDocument;
  const reviewed = state.reviewed;
  const confirmed = reviewed.filter((r) => r.confirmed).length;
  const needsReview = reviewed.filter((r) => r.needs_review && !r.confirmed).length;
  const noMatch = reviewed.filter((r) => !r.approved_element).length;
  const allConfirmed = confirmed === reviewed.length;

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Quoter Motor</h1>
          <p className="text-slate-500 text-sm mt-1">
            Recreate a Flex quote with current gear and pricing
          </p>
        </div>

        <StepNav current={1} />

        {/* Source doc header */}
        <div className="mb-4 p-4 bg-surface-card border border-surface-border rounded-lg flex flex-wrap gap-4 items-start">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider">Source Quote</div>
            <div className="font-mono text-sky-400 text-sm mt-0.5">
              {doc.documentNumber ?? doc.id}
            </div>
          </div>
          {doc.description && (
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider">Description</div>
              <div className="text-sm text-slate-300 mt-0.5">{doc.description}</div>
            </div>
          )}
          {doc.clientName && (
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider">Client</div>
              <div className="text-sm text-slate-300 mt-0.5">{doc.clientName}</div>
            </div>
          )}
          <div className="ml-auto flex gap-4 text-sm text-right">
            <Stat label="Items" value={reviewed.length} />
            <Stat label="Confirmed" value={confirmed} color="text-emerald-400" />
            <Stat label="Needs Review" value={needsReview} color="text-amber-400" />
            {noMatch > 0 && <Stat label="No Match" value={noMatch} color="text-red-400" />}
          </div>
        </div>

        {/* Column headers */}
        <div className="grid grid-cols-[2.5rem_1fr_2rem_1fr_6rem_5rem_5rem] gap-2 px-3 py-1.5 text-xs text-slate-600 uppercase tracking-wider mb-1">
          <span className="text-right">#</span>
          <span>Old Item</span>
          <span />
          <span>New Item</span>
          <span className="text-center">Confidence</span>
          <span className="text-right">Qty</span>
          <span className="text-right">Action</span>
        </div>

        {/* Item rows */}
        <div>
          {reviewed.map((match, i) => (
            <ItemMatchRow
              key={i}
              match={match}
              index={i}
              onApprove={(element: FlexElement) =>
                dispatch({ type: "APPROVE_MATCH", index: i, element })
              }
              onSetQty={(qty: number) => dispatch({ type: "SET_QTY", index: i, qty })}
              onConfirm={(confirmed: boolean) =>
                dispatch({ type: "CONFIRM_ROW", index: i, confirmed })
              }
            />
          ))}
        </div>

        {/* Footer actions */}
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => dispatch({ type: "CONFIRM_ALL" })}
            className="text-sm text-slate-400 hover:text-slate-200 underline"
          >
            Approve all matched items
          </button>
          <div className="flex gap-3">
            <button
              onClick={() => navigate("/")}
              className="px-4 py-2 border border-surface-border rounded text-sm text-slate-400 hover:border-slate-500 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={() => navigate("/details")}
              disabled={confirmed === 0}
              className={clsx(
                "px-5 py-2 rounded text-sm font-medium transition-colors",
                confirmed > 0
                  ? "bg-sky-600 hover:bg-sky-700 text-white"
                  : "bg-surface border border-surface-border text-slate-600 cursor-not-allowed"
              )}
            >
              Next: Quote Details →
              {!allConfirmed && confirmed > 0 && (
                <span className="ml-2 text-sky-300 text-xs">({confirmed} items)</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  color = "text-slate-200",
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div>
      <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
      <div className={clsx("text-lg font-mono font-semibold mt-0.5", color)}>{value}</div>
    </div>
  );
}
