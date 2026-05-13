import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  previewQuote,
  itemQty,
  itemRate,
  itemExtended,
  itemNote,
  type QuotePreviewResponse,
} from "@/api/client";
import { useQuoteStore } from "@/store/quoteStore";
import { StepNav } from "@/components/StepNav";

export function Diff() {
  const { state } = useQuoteStore();
  const navigate = useNavigate();

  const [preview, setPreview] = useState<QuotePreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadPreview() {
      try {
        const approvedItems = state.reviewed
          .filter((r) => r.confirmed && r.approved_element)
          .map((r, i) => ({
            element_id: r.approved_element!.id,
            quantity: r.override_qty ?? itemQty(r.old_item),
            unit_price: itemRate(r.old_item),
            note: itemNote(r.old_item),
            sort_order: i,
            class_name: (r.approved_element!.className as string) ?? undefined,
            old_item: r.old_item,
            approved_name: r.approved_element!.name,
          }));

        const result = await previewQuote({
          description: state.newDescription,
          client_id: state.newClientId || undefined,
          start_date: state.newStartDate || undefined,
          end_date: state.newEndDate || undefined,
          items: approvedItems,
        });

        setPreview(result);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to build preview");
      } finally {
        setLoading(false);
      }
    }

    loadPreview();
  }, [state]);

  if (!state.sourceDocument) {
    navigate("/");
    return null;
  }

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Quoter Motor</h1>
          <p className="text-slate-500 text-sm mt-1">
            Review export validation and quote differences before pushing to Flex
          </p>
        </div>

        <StepNav current={3} />

        {loading && (
          <div className="text-slate-400 text-sm">Building export preview…</div>
        )}

        {error && (
          <div className="bg-red-950 border border-red-800 rounded p-4 text-red-300 text-sm">
            {error}
          </div>
        )}

        {preview && (
          <div className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <Card>
                <Label>Original Total</Label>
                <Value>${format(preview.totals.old_total)}</Value>
              </Card>
              <Card>
                <Label>Projected Total</Label>
                <Value>${format(preview.totals.new_total)}</Value>
              </Card>
              <Card>
                <Label>Difference</Label>
                <Value>${format(preview.totals.delta)}</Value>
              </Card>
            </div>

            <Card>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">
                  Validation
                </h2>
                <span
                  className={preview.valid ? "text-emerald-400 text-sm" : "text-amber-400 text-sm"}
                >
                  {preview.valid ? "Ready to export" : "Review recommended"}
                </span>
              </div>

              <div className="space-y-2">
                {preview.issues.map((issue, i) => (
                  <div
                    key={i}
                    className="rounded border border-surface-border bg-surface px-3 py-2 text-sm"
                  >
                    <span
                      className={
                        issue.level === "error"
                          ? "text-red-400"
                          : issue.level === "warning"
                          ? "text-amber-400"
                          : "text-sky-400"
                      }
                    >
                      {issue.level.toUpperCase()}
                    </span>
                    <span className="text-slate-300 ml-2">{issue.message}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400 mb-3">
                Planned Flex Operations
              </h2>

              <div className="space-y-2 text-sm font-mono text-slate-300">
                {preview.planned_operations.map((op, i) => (
                  <div key={i}>{op}</div>
                ))}
              </div>
            </Card>

            <Card>
              <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400 mb-3">
                Quote Diff View
              </h2>

              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border text-slate-500">
                      <th className="text-left py-2">Original</th>
                      <th className="text-left py-2">Replacement</th>
                      <th className="text-right py-2">Qty</th>
                      <th className="text-right py-2">Old Total</th>
                      <th className="text-right py-2">New Total</th>
                      <th className="text-right py-2">Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.diff.map((row) => (
                      <tr key={row.index} className="border-b border-surface-border/40">
                        <td className="py-2 text-slate-300">{row.old_name}</td>
                        <td className="py-2 text-slate-200">{row.new_name}</td>
                        <td className="py-2 text-right font-mono">{row.quantity}</td>
                        <td className="py-2 text-right font-mono">
                          ${format(row.old_extended)}
                        </td>
                        <td className="py-2 text-right font-mono">
                          ${format(row.new_extended)}
                        </td>
                        <td
                          className={`py-2 text-right font-mono ${
                            (row.delta ?? 0) > 0
                              ? "text-amber-400"
                              : (row.delta ?? 0) < 0
                              ? "text-emerald-400"
                              : "text-slate-400"
                          }`}
                        >
                          ${format(row.delta)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="flex justify-between">
              <button
                onClick={() => navigate("/details")}
                className="px-4 py-2 border border-surface-border rounded text-sm text-slate-400 hover:border-slate-500"
              >
                ← Back to Details
              </button>

              <button
                onClick={() => navigate("/success")}
                className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-medium"
              >
                Continue to Export →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function format(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "0.00";
  return Number(value).toFixed(2);
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg p-4">
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{children}</div>
  );
}

function Value({ children }: { children: React.ReactNode }) {
  return <div className="text-xl font-mono text-slate-100">{children}</div>;
}
