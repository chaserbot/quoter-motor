import { useState } from "react";
import clsx from "clsx";
import { ConfidenceBadge, confidenceColor } from "./ConfidenceBadge";
import { InventorySearch } from "./InventorySearch";
import { itemName, itemQty, itemRate, type FlexElement } from "@/api/client";
import type { ReviewedMatch } from "@/store/quoteStore";

interface Props {
  match: ReviewedMatch;
  index: number;
  onApprove: (element: FlexElement) => void;
  onSetQty: (qty: number) => void;
  onConfirm: (confirmed: boolean) => void;
}

export function ItemMatchRow({ match, index, onApprove, onSetQty, onConfirm }: Props) {
  const [showSearch, setShowSearch] = useState(false);
  const [showAlts, setShowAlts] = useState(false);

  const old = match.old_item;
  const approved = match.approved_element;
  const qty = match.override_qty ?? itemQty(old);
  const rate = approved?.defaultPrice ?? itemRate(old);

  const rowBorder = match.confirmed
    ? "border-l-emerald-500"
    : match.needs_review
    ? "border-l-orange-500"
    : "border-l-slate-600";

  return (
    <div
      className={clsx(
        "border border-surface-border border-l-4 rounded bg-surface-card mb-2 transition-colors",
        rowBorder
      )}
    >
      {/* Main row */}
      <div className="grid grid-cols-[2.5rem_1fr_2rem_1fr_6rem_5rem_5rem] gap-2 items-center px-3 py-2">
        {/* Row number */}
        <span className="text-slate-600 text-xs font-mono text-right">{index + 1}</span>

        {/* Old item */}
        <div className="min-w-0">
          <div className="text-sm text-slate-300 truncate">{itemName(old)}</div>
          {old.elementTypeName && (
            <div className="text-xs text-slate-600 truncate">{old.elementTypeName as string}</div>
          )}
        </div>

        {/* Arrow */}
        <span className="text-slate-600 text-center">→</span>

        {/* Approved item */}
        <div className="min-w-0">
          {approved ? (
            <>
              <div className="text-sm text-slate-200 truncate">{approved.name}</div>
              {approved.elementTypeName && (
                <div className="text-xs text-slate-600 truncate">{approved.elementTypeName}</div>
              )}
            </>
          ) : (
            <span className="text-sm text-red-400 italic">No match</span>
          )}
        </div>

        {/* Confidence */}
        <div className="flex justify-center">
          <ConfidenceBadge confidence={match.confidence} showPercent />
        </div>

        {/* Qty */}
        <div>
          <input
            type="number"
            min={0}
            step={1}
            value={qty}
            onChange={(e) => onSetQty(Number(e.target.value))}
            className="w-full bg-surface border border-surface-border rounded px-2 py-0.5 text-sm text-slate-200 font-mono text-right focus:outline-none focus:border-sky-500"
          />
        </div>

        {/* Confirm toggle */}
        <div className="flex justify-end">
          <button
            onClick={() => onConfirm(!match.confirmed)}
            disabled={!approved}
            className={clsx(
              "px-3 py-1 rounded text-xs font-medium transition-colors",
              match.confirmed
                ? "bg-emerald-600 text-white hover:bg-emerald-700"
                : "bg-surface border border-surface-border text-slate-400 hover:border-sky-500 hover:text-sky-400"
            )}
          >
            {match.confirmed ? "✓ OK" : "Approve"}
          </button>
        </div>
      </div>

      {/* Reason + actions */}
      {(match.needs_review || showSearch || showAlts) && (
        <div className="px-4 pb-3 space-y-2 border-t border-surface-border">
          {/* AI reason */}
          {match.reason && (
            <p className="text-xs text-slate-500 pt-2 italic">{match.reason}</p>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            <button
              className="text-xs text-sky-400 hover:text-sky-300 underline"
              onClick={() => { setShowSearch(!showSearch); setShowAlts(false); }}
            >
              {showSearch ? "Hide search" : "Override item"}
            </button>
            {match.alternatives.length > 0 && (
              <button
                className="text-xs text-slate-400 hover:text-slate-300 underline"
                onClick={() => { setShowAlts(!showAlts); setShowSearch(false); }}
              >
                {showAlts ? "Hide alternatives" : `${match.alternatives.length} alternatives`}
              </button>
            )}
          </div>

          {/* Search override */}
          {showSearch && (
            <InventorySearch
              onSelect={(item) => {
                onApprove(item);
                setShowSearch(false);
              }}
              placeholder="Search inventory to override…"
            />
          )}

          {/* Alternatives */}
          {showAlts && (
            <div className="flex flex-col gap-1">
              {match.alternatives.map((alt) => (
                <button
                  key={alt.id}
                  onClick={() => { onApprove(alt); setShowAlts(false); }}
                  className="flex items-center gap-2 text-left px-2 py-1 rounded hover:bg-surface-border text-sm text-slate-300 transition-colors"
                >
                  <span className="text-sky-500 text-xs">→</span>
                  {alt.name}
                  {alt.elementTypeName && (
                    <span className="text-xs text-slate-600">{alt.elementTypeName}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
