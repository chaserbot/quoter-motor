# Quoter Motor — Agent Handoff Guide

A self-hosted web tool for recreating Flex Rental Solutions quotes with current inventory.
The goal: load an old quote, review each line item matched to current gear, approve/override, push a new quote to Flex.

---

## What works today

- **Quote search**: searches across all Flex elements, cached in memory, matches on quote number or event name
- **Match flow**: loads source quote's line items, resolves each `resourceId` against live inventory via `managed-resource/identity`, returns 100% confidence for items still in inventory
- **Review UI**: per-item approve/skip, quantity override, manual inventory search (type ≥2 chars to search), confidence badges
- **Create quote**: creates a new Flex Quote document with correct definition, sets USD currency, adds all approved items as line items
- **Mixed item types**: handles both `INVENTORY_MODEL` (gear) and `SERVICE_OFFERING` (labor) correctly

---

## What needs work (known issues)

### 1. No subtotal structure
Items are added flat to the root of the new document. The source quote may have subtotal groups (e.g., "Lighting", "Audio", "Power"). The current `_flatten_line_items()` in `client.py` discards the tree structure. To fix: preserve the group/subtotal structure from the source quote, create subtotal line items first, then add children under them using `parentLineItemId` query param on `add-resource`.

### 2. Pricing model not copied
When items are added via `add-resource`, Flex uses the item's default catalog rate. The source quote may have had custom or negotiated prices. To fix: after `add-resource` returns `addedResourceLineIds`, call `PUT /api/line-item/{elementId}/update` with `fieldType=priceEach` and `payloadValue=<price>` for each main line item. The `affectedRootLineIds` field in the add-resource response identifies the main (root) line item ID.

### 3. Rental period / defaultTime not copied
Each quote has a `defaultTime` (number) and `defaultPricingModelId` (e.g., "Week" = `7453304c-aee0-11df-b8d5-00e08175e43e`). These control how pricing is calculated against the rental duration. Currently we copy the dates but not `defaultTime` or `defaultPricingModelId`. To fix: fetch these from the source quote's `header-data`, then set them via `header-update` on the new document (same `fieldType: defaultTime / defaultPricingModelId` pattern used for currency).

### 4. Items without resourceId
Custom line items (manually typed in Flex — "Piano Tuning", "Pelleted Dry Ice") have no `resourceId` and cannot be auto-matched. They show as `needs_review: True` with reason "No resourceId on line item". The user must manually find a replacement via inventory search. This is acceptable behavior; just make sure the UI communicates it clearly.

---

## Flex API — verified endpoints

Auth: `X-Auth-Token: <api_key>` header on every request. Key is in `.env` as `FLEX_API_KEY`.
Base URL: `https://clearlamp.flexrentalsolutions.com/f5`
Swagger: `https://clearlamp.flexrentalsolutions.com/f5/swagger-ui/index.html` (OAS3)
Raw spec: `GET /f5/v3/api-docs` (authenticated)

### Endpoints in use

| Endpoint | Purpose |
|---|---|
| `GET /api/element/search?searchText=&size=1000&page=N` | Paginated load of all elements (quotes, events, etc.) for quote search cache |
| `GET /api/element/{id}/header-data?codeList=field1,field2` | Fetch document header fields |
| `POST /api/element/{id}/header-update` body `{fieldType, payloadValue}` | Update a single header field (currency, dates, etc.) |
| `GET /api/financial-document-line-item/{docId}/row-data/?node=root&codeList=...` | Fetch line items as a tree from a quote |
| `GET /api/managed-resource/{resourceId}/identity` | Look up a single inventory model or service offering by ID — **this is how resourceId from line items is resolved** |
| `GET /api/inventory-model/search?searchText=query&size=50` | Search inventory models by name (min 2 chars) — used for manual override search |
| `POST /api/element` body `ElementPersistRequest` | Create a new document (quote) |
| `POST /api/line-item/{docId}/add-resource/{resourceId}?resourceParentId={docId}&managedResourceLineItemType=inventory-model&quantity=N` | Add a line item to a document |

### Critical API discoveries (learned the hard way)

- `element/search` returns ALL Flex elements (quotes, events, manifests, inventory) — **not** just inventory. The old code tried to use this for inventory matching and got ~10k garbage results.
- `resourceId` on a quote line item is an **inventory-model or service-offering ID**, not an element ID. Look it up via `managed-resource/{id}/identity`, not `element/{id}`.
- `inventory-model/search` requires `searchText` to be ≥ 2 characters or it returns 400.
- Creating a document via `POST /api/element` does **not** set currency — you must follow up with `POST /api/element/{id}/header-update` with `fieldType: currencyId`. Without this, adding `service-offering` line items fails with "does not have a currency set" (inventory-model adds work even without currency set, which is confusing).
- `financial-document-line-item/{docId}/add-resource/{resourceId}` fails for `service-offering` type with "no currency" even when currency is set. Use `line-item/{docId}/add-resource/{resourceId}` instead — it works for both `inventory-model` and `service-offering`.
- `managed-resource/identity` returns `className` field: `INVENTORY_MODEL` for gear, `SERVICE_OFFERING` for labor. Map this to `managedResourceLineItemType` query param via `CLASS_TO_LINE_ITEM_TYPE` dict in `client.py`.
- `add-resource` accepts quantity as a **query param**, not in the JSON body. The response includes `addedResourceLineIds` (all added lines, including auto-added accessories) and `affectedRootLineIds` (just the main item).
- `element/search` correct param is `searchText` (not `searchString` — the old name silently ignored the filter and returned everything).
- The Quote definition ID is `9bfb850c-b117-11df-b8d5-00e08175e43e`. Must be passed as `definitionId` when creating a quote.
- USD currency ID is `911e3d4c-aedc-11df-b8d5-00e08175e43e`.

---

## Architecture

```
quoter-motor/
├── backend/                   FastAPI Python app
│   ├── app/
│   │   ├── config.py          Settings from .env (pydantic-settings)
│   │   ├── main.py            FastAPI app + CORS + router registration + background cache warm
│   │   ├── flex/
│   │   │   └── client.py      All Flex API calls — see inline comments for why each endpoint is used
│   │   ├── matching/
│   │   │   └── engine.py      Fuzzy name matching (unused in main flow; kept for fallback)
│   │   └── routes/
│   │       ├── quotes.py      /api/quotes/search, /match, /create
│   │       ├── inventory.py   /api/inventory/search
│   │       └── debug.py       /api/debug/flex-connection
│   └── Dockerfile
├── frontend/                  React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── api/client.ts      Axios client + all TS types
│   │   ├── store/quoteStore.ts React context + reducer
│   │   ├── components/
│   │   │   ├── ConfidenceBadge.tsx
│   │   │   ├── ItemMatchRow.tsx    Review row: approve/skip, qty override, alt picker
│   │   │   ├── InventorySearch.tsx Debounced live search for manual override
│   │   │   └── StepNav.tsx
│   │   └── pages/
│   │       ├── Home.tsx        Step 1: search + load source quote
│   │       ├── Review.tsx      Step 2: review matches
│   │       ├── Details.tsx     Step 3: name/dates/client for new quote
│   │       └── Success.tsx     Step 4: confirmation + link to new quote in Flex
│   ├── nginx.conf             Proxies /api/ → backend:8000
│   └── Dockerfile
├── docker-compose.yml         Frontend :3000 (nginx), backend internal
├── .env.example
└── AGENTS.md                  This file
```

### Match flow (the core)

1. User searches for a source quote → `GET /api/quotes/search?q=...` → searches cached element list
2. User selects a quote → `POST /api/quotes/match` → fetches line items, resolves each `resourceId` via `managed-resource/identity`
3. Items still in inventory → `confidence: 1.0, needs_review: false`
4. Items removed from inventory → `confidence: 0.0, needs_review: true` (user must pick manually)
5. Items with no `resourceId` (manually typed in original) → `needs_review: true`
6. User reviews, approves, overrides quantities
7. User fills Details form → `POST /api/quotes/create` → creates doc, sets currency, adds all approved items
8. Success page shows link to open new quote in Flex

### State management

Single React context (`quoteStore.ts`) with reducer. State shape:
```ts
{
  sourceDocument: FlexDocument | null,
  matches: MatchResult[],           // from /match endpoint
  reviewed: ReviewedItem[],         // user decisions (approved_element, override_qty, confirmed)
  newDescription, newClientId, newStartDate, newEndDate,  // Details form
  createdDocId, createdDocNumber,   // after successful create
}
```

---

## Running locally

```bash
cp .env.example .env
# Fill in FLEX_BASE_URL and FLEX_API_KEY (get key from Flex → Integrations → API)
docker compose up --build
# http://localhost:3000
```

Backend has hot-reload: `backend/app/` is volume-mounted, uvicorn reloads on file changes.

## Deploy to Proxmox

```bash
git clone git@github.com:chaserbot/quoter-motor.git
cd quoter-motor
cp .env.example .env   # fill in credentials
docker compose up -d --build
# http://VM_IP:3000
```

## Required .env vars

| Variable | Description |
|---|---|
| `FLEX_BASE_URL` | `https://clearlamp.flexrentalsolutions.com/f5` |
| `FLEX_API_KEY` | From Flex → Integrations → API |
| `OPENAI_API_KEY` | Not currently used in main flow; kept for future AI matching phase |
