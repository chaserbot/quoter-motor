/**
 * Simple React context + reducer store — no external state lib needed.
 * Holds the matched quote data and user's approved selections across steps.
 */

import { createContext, useContext, useReducer, Dispatch } from "react";
import type { FlexDocument, FlexElement, MatchResult } from "@/api/client";

export interface ReviewedMatch extends MatchResult {
  /** The element the user has approved (may differ from AI match) */
  approved_element: FlexElement | null;
  /** User confirmed this row is ready */
  confirmed: boolean;
  /** Override quantity set by user (falls back to old_item quantity) */
  override_qty?: number;
}

export interface QuoteState {
  sourceDocument: FlexDocument | null;
  reviewed: ReviewedMatch[];
  newDescription: string;
  newClientId: string;
  newStartDate: string;
  newEndDate: string;
  createdDocId: string | null;
  createdDocNumber: string | null;
}

const initial: QuoteState = {
  sourceDocument: null,
  reviewed: [],
  newDescription: "",
  newClientId: "",
  newStartDate: "",
  newEndDate: "",
  createdDocId: null,
  createdDocNumber: null,
};

function dateInputValue(value: unknown): string {
  if (typeof value !== "string" || !value) return "";
  return value.slice(0, 10);
}

type Action =
  | { type: "SET_MATCH_RESULTS"; document: FlexDocument; matches: MatchResult[] }
  | { type: "APPROVE_MATCH"; index: number; element: FlexElement }
  | { type: "SET_QTY"; index: number; qty: number }
  | { type: "CONFIRM_ROW"; index: number; confirmed: boolean }
  | { type: "CONFIRM_ALL" }
  | { type: "SET_NEW_DESCRIPTION"; value: string }
  | { type: "SET_NEW_CLIENT_ID"; value: string }
  | { type: "SET_NEW_START_DATE"; value: string }
  | { type: "SET_NEW_END_DATE"; value: string }
  | { type: "SET_CREATED"; docId: string; docNumber?: string }
  | { type: "RESET" };

function reducer(state: QuoteState, action: Action): QuoteState {
  switch (action.type) {
    case "SET_MATCH_RESULTS":
      return {
        ...state,
        sourceDocument: action.document,
        newDescription: action.document.description
          ? `${action.document.description} — COPY`
          : "",
        newClientId: action.document.clientId ?? "",
        newStartDate: dateInputValue(action.document.startDateTime),
        newEndDate: dateInputValue(action.document.endDateTime),
        reviewed: action.matches.map((m) => ({
          ...m,
          approved_element: m.match,
          confirmed: !m.needs_review && m.match !== null,
        })),
      };

    case "APPROVE_MATCH":
      return {
        ...state,
        reviewed: state.reviewed.map((r, i) =>
          i === action.index
            ? { ...r, approved_element: action.element, confirmed: true }
            : r
        ),
      };

    case "SET_QTY":
      return {
        ...state,
        reviewed: state.reviewed.map((r, i) =>
          i === action.index ? { ...r, override_qty: action.qty } : r
        ),
      };

    case "CONFIRM_ROW":
      return {
        ...state,
        reviewed: state.reviewed.map((r, i) =>
          i === action.index ? { ...r, confirmed: action.confirmed } : r
        ),
      };

    case "CONFIRM_ALL":
      return {
        ...state,
        reviewed: state.reviewed.map((r) =>
          r.approved_element ? { ...r, confirmed: true } : r
        ),
      };

    case "SET_NEW_DESCRIPTION":
      return { ...state, newDescription: action.value };
    case "SET_NEW_CLIENT_ID":
      return { ...state, newClientId: action.value };
    case "SET_NEW_START_DATE":
      return { ...state, newStartDate: action.value };
    case "SET_NEW_END_DATE":
      return { ...state, newEndDate: action.value };

    case "SET_CREATED":
      return { ...state, createdDocId: action.docId, createdDocNumber: action.docNumber ?? null };

    case "RESET":
      return initial;
  }
}

// ----------------------------------------------------------------- context

export const QuoteContext = createContext<{
  state: QuoteState;
  dispatch: Dispatch<Action>;
} | null>(null);

export function useQuoteStore() {
  const ctx = useContext(QuoteContext);
  if (!ctx) throw new Error("useQuoteStore must be inside QuoteProvider");
  return ctx;
}

export function useQuoteReducer() {
  return useReducer(reducer, initial);
}
