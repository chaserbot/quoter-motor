import { useNavigate } from "react-router-dom";
import { useQuoteStore } from "@/store/quoteStore";
import { itemQty } from "@/api/client";
import { StepNav } from "@/components/StepNav";

export function Details() {
  const { state, dispatch } = useQuoteStore();
  const navigate = useNavigate();

  if (!state.sourceDocument) {
    navigate("/");
    return null;
  }

  const approvedItems = state.reviewed.filter((r) => r.confirmed && r.approved_element);

  function handleContinue(e: React.FormEvent) {
    e.preventDefault();
    if (!state.newDescription.trim()) return;

    navigate("/diff");
  }

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Quoter Motor</h1>
          <p className="text-slate-500 text-sm mt-1">
            Recreate a Flex quote with current gear and pricing
          </p>
        </div>

        <StepNav current={2} />

        <form onSubmit={handleContinue} className="space-y-4">
          <div className="bg-surface-card border border-surface-border rounded-lg p-6 space-y-4">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
              New Quote Details
            </h2>

            <Field label="Description *">
              <input
                required
                className={input}
                value={state.newDescription}
                onChange={(e) => dispatch({ type: "SET_NEW_DESCRIPTION", value: e.target.value })}
                placeholder="Event name / quote description"
              />
            </Field>

            <Field label="Client ID">
              <input
                className={input}
                value={state.newClientId}
                onChange={(e) => dispatch({ type: "SET_NEW_CLIENT_ID", value: e.target.value })}
                placeholder="Leave blank to use source quote's client"
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Start Date">
                <input
                  type="date"
                  className={input}
                  value={state.newStartDate}
                  onChange={(e) =>
                    dispatch({ type: "SET_NEW_START_DATE", value: e.target.value })
                  }
                />
              </Field>
              <Field label="End Date">
                <input
                  type="date"
                  className={input}
                  value={state.newEndDate}
                  onChange={(e) =>
                    dispatch({ type: "SET_NEW_END_DATE", value: e.target.value })
                  }
                />
              </Field>
            </div>
          </div>

          <div className="bg-surface-card border border-surface-border rounded-lg p-4 text-sm">
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Items to create</span>
              <span className="font-mono text-slate-200">{approvedItems.length}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Estimated quantity total</span>
              <span className="font-mono">
                {approvedItems.reduce(
                  (sum, r) => sum + (r.override_qty ?? itemQty(r.old_item)),
                  0
                )}
              </span>
            </div>
          </div>

          <div className="flex gap-3 justify-between">
            <button
              type="button"
              onClick={() => navigate("/review")}
              className="px-4 py-2 border border-surface-border rounded text-sm text-slate-400 hover:border-slate-500 transition-colors"
            >
              ← Back to Review
            </button>
            <button
              type="submit"
              disabled={approvedItems.length === 0}
              className="px-6 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white text-sm font-medium rounded transition-colors"
            >
              Continue to Diff Review →
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const input =
  "w-full bg-surface border border-surface-border rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
