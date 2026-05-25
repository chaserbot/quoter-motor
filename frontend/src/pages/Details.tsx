import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuoteStore } from "@/store/quoteStore";
import { createQuote, itemQty, itemRate } from "@/api/client";
import { StepNav } from "@/components/StepNav";

export function Details() {
  const { state, dispatch } = useQuoteStore();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!state.sourceDocument) {
    navigate("/");
    return null;
  }

  const approvedItems = state.reviewed.filter((r) => r.confirmed && r.approved_element);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!state.newDescription.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      const result = await createQuote({
        description: state.newDescription,
        client_id: state.newClientId || undefined,
        start_date: state.newStartDate || undefined,
        end_date: state.newEndDate || undefined,
        default_time: state.sourceDocument.defaultTime,
        default_pricing_model_id: flexId(state.sourceDocument.defaultPricingModelId),
        items: approvedItems.map((r, i) => ({
          element_id: r.approved_element!.id,
          quantity: r.override_qty ?? itemQty(r.old_item),
          unit_price: itemRate(r.old_item),
          note: (r.old_item.note as string) || undefined,
          sort_order: i,
          class_name: (r.approved_element!.className as string) ?? undefined,
        })),
      });

      dispatch({
        type: "SET_CREATED",
        docId: result.document_id,
        docNumber: result.document_number,
      });
      navigate("/success");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create quote");
    } finally {
      setSubmitting(false);
    }
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

        <form onSubmit={handleSubmit} className="space-y-4">
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

          {/* Summary */}
          <div className="bg-surface-card border border-surface-border rounded-lg p-4 text-sm">
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Items to create</span>
              <span className="font-mono text-slate-200">{approvedItems.length}</span>
            </div>
            {state.reviewed.length - approvedItems.length > 0 && (
              <div className="flex justify-between text-slate-500">
                <span>Skipped (not approved)</span>
                <span className="font-mono">
                  {state.reviewed.length - approvedItems.length}
                </span>
              </div>
            )}
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

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
              disabled={submitting || approvedItems.length === 0}
              className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white text-sm font-medium rounded transition-colors"
            >
              {submitting ? "Creating in Flex…" : `Push ${approvedItems.length} items to Flex →`}
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

function flexId(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "id" in value) {
    const id = (value as { id?: unknown }).id;
    return typeof id === "string" ? id : undefined;
  }
  return undefined;
}
