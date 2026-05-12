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
  inventory_size: number;
  needs_review_count: number;
}

export interface ApprovedItem {
  element_id: string;
  quantity: number;
  unit_price?: number;
  note?: string;
  sort_order?: number;
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

// ---------------------------------------------------------------- helpers

export function itemName(item: Record<string, unknown>): string {
  return (
    (item.elementName as string) ||
    (item.name as string) ||
    (item.description as string) ||
    "Unknown item"
  );
}

export function itemQty(item: Record<string, unknown>): number {
  return Number(item.quantity) || 1;
}

export function itemRate(item: Record<string, unknown>): number | undefined {
  const v = item.unitPrice ?? item.rate ?? item.defaultPrice;
  return v !== undefined ? Number(v) : undefined;
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

export async function createQuote(payload: CreateQuoteRequest): Promise<CreateQuoteResponse> {
  const { data } = await api.post<CreateQuoteResponse>("/quotes/create", payload);
  return data;
}

export async function checkFlexConnection() {
  const { data } = await api.get("/debug/flex-connection");
  return data;
}
