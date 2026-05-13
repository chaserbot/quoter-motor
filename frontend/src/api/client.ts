import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

// ------------------------------------------------------------------ types

export interface FlexDocument {
  id: string;
  documentNumber?: string;
  description?: string;
  clientId?: string;
  clientName?: string;
  startDateTime?: string;
  endDateTime?: string;
  totalPrice?: number;
  [key: string]: unknown;
}

export interface FlexElement {
  id: string;
  name?: string;
  description?: string;
  elementTypeId?: string;
  elementTypeName?: string;
  categoryId?: string;
  categoryName?: string;
  className?: string;
  defaultPrice?: number;
  [key: string]: unknown;
}

export interface MatchResult {
  old_item: Record<string, unknown>;
  match: FlexElement | null;
  confidence: number;
  reason: string;
  alternatives: FlexElement[];
  needs_review: boolean;
}

export interface MatchResponse {
  document: FlexDocument;
  matches: MatchResult[];
  inventory_size?: number;
  needs_review_count: number;
}

export interface ApprovedItem {
  element_id: string;
  quantity: number;
  unit_price?: number;
  note?: string;
  sort_order?: number;
  class_name?: string;
  old_item?: Record<string, unknown>;
  approved_name?: string;
}

export interface CreateQuoteRequest {
  description: string;
  client_id?: string;
  start_date?: string;
  end_date?: string;
  items: ApprovedItem[];
}

export interface CreateQuoteResponse {
  document: FlexDocument;
  document_id: string;
  document_number?: string;
  items_created: number;
  items_failed: number;
  failures: unknown[];
}

export interface QuoteValidationIssue {
  level: "error" | "warning" | "info";
  message: string;
  item_index?: number;
}

export interface QuoteDiffRow {
  index: number;
  old_name: string;
  new_name: string;
  quantity: number;
  old_unit_price?: number;
  new_unit_price?: number;
  old_extended?: number;
  new_extended?: number;
  delta?: number;
  note?: string;
}

export interface QuotePreviewResponse {
  valid: boolean;
  issues: QuoteValidationIssue[];
  diff: QuoteDiffRow[];
  planned_operations: string[];
  totals: {
    old_total?: number;
    new_total?: number;
    delta?: number;
  };
}

// ---------------------------------------------------------------- helpers

function unwrapField(value: unknown): unknown {
  if (
    value &&
    typeof value === "object" &&
    "data" in value &&
    Object.keys(value as Record<string, unknown>).length <= 3
  ) {
    return (value as { data?: unknown }).data;
  }
  return value;
}

function readString(item: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = unwrapField(item[key]);
    if (typeof value === "string" && value.trim()) return value;
    if (value && typeof value === "object") {
      const obj = value as Record<string, unknown>;
      const display = obj.preferredDisplayString ?? obj.name ?? obj.description;
      if (typeof display === "string" && display.trim()) return display;
    }
  }
  return undefined;
}

function readNumber(item: Record<string, unknown>, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = unwrapField(item[key]);
    if (value === null || value === undefined || value === "") continue;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

export function itemName(item: Record<string, unknown>): string {
  return (
    readString(item, ["elementName", "name", "description", "resourceName"]) ??
    "Unknown item"
  );
}

export function itemQty(item: Record<string, unknown>): number {
  return readNumber(item, ["quantity", "qty"]) ?? 1;
}

export function itemRate(item: Record<string, unknown>): number | undefined {
  return readNumber(item, [
    "priceEach",
    "unitPrice",
    "rate",
    "defaultPrice",
    "price",
  ]);
}

export function itemExtended(item: Record<string, unknown>): number | undefined {
  return readNumber(item, ["priceExtended", "extendedPrice", "totalPrice"]);
}

export function itemNote(item: Record<string, unknown>): string | undefined {
  return readString(item, ["note", "notes", "description"]);
}

// ---------------------------------------------------------------- API calls

export async function fetchMatchedQuote(sourceId: string): Promise<MatchResponse> {
  const { data } = await api.post<MatchResponse>("/quotes/match", {
    source_quote_id: sourceId,
  });
  return data;
}

export async function searchQuotes(q: string) {
  const { data } = await api.get("/quotes/search", { params: { q } });
  return data.results as FlexDocument[];
}

export async function searchInventory(q: string): Promise<FlexElement[]> {
  const { data } = await api.get("/inventory/search", { params: { q } });
  return data.items as FlexElement[];
}

export async function previewQuote(payload: CreateQuoteRequest): Promise<QuotePreviewResponse> {
  const { data } = await api.post<QuotePreviewResponse>("/quotes/preview", payload);
  return data;
}

export async function createQuote(payload: CreateQuoteRequest): Promise<CreateQuoteResponse> {
  const { data } = await api.post<CreateQuoteResponse>("/quotes/create", payload);
  return data;
}

export async function checkFlexConnection() {
  const { data } = await api.get("/debug/flex-connection");
  return data;
}
