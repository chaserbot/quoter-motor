# Flex Rental Solutions API + MCP Research Notes

Date: 2026-05-13
Branch: quote-tree-export-cleanup

## Executive summary

Flex is usable for automation, but it should be treated as a semi-documented, beta API.

The right direction for Quoter Motor is:

1. Keep the current FastAPI app as the production web UI.
2. Add a Flex API service layer that is clean, typed, cached, and heavily logged.
3. Add an optional MCP server as an AI-facing interface to that same service layer.
4. Keep quote creation/export guarded by preview, validation, and human approval.

Do not let an AI directly create or mutate quotes without a human-confirmed preview step.

## Public Flex facts found

### Flex5 API status

Flex Rental Solutions states that the Flex5 API is currently in Beta and requires API access approval plus acceptance of API terms.

Implication:
- Expect incomplete docs.
- Expect endpoint quirks.
- Build defensive wrappers.
- Log every export operation in human-readable form.

### API authentication

Flex API authentication uses an API key sent as:

```http
X-Auth-Token: <api_key>
```

This matches the current Quoter Motor code.

### API permissions

Flex API keys inherit the permissions of the user who generated the key.

Implication:
- Create a dedicated Flex user for automation.
- Give that user only the permissions needed for quote search, inventory lookup, and quote creation.
- Do not use a full-admin personal key for production.

### API limits

Flex publishes request limits by plan.

For Enterprise/GTS:
- 100,000 monthly
- 10,000 daily
- 2,000 hourly
- concurrency limit of 30 simultaneous requests per customer
- 429 is used for rate limiting

Implication:
- Current one-call-per-line-item matching is acceptable for small quotes but should be deduped and cached.
- Never do blind background scans every few minutes.
- Add retry/backoff only for safe GET calls.

### Swagger is not enough

Flex says Swagger UI does not document all request parameter codes and JSON body structures.

Flex recommends using browser DevTools Network tab while operating the Flex web app to observe real API calls.

Implication:
- For subtotal/group creation and parent-child line item export, use the Flex UI as the source of truth.
- Record the exact network calls when manually creating:
  - a subtotal group
  - a nested child line item
  - a price override
  - a pricing model override
  - defaultTime/defaultPricingModelId changes

## What this means for Quoter Motor

### Current good decisions

The current code is already aligned with these Flex facts:

- uses X-Auth-Token
- uses live Flex API rather than scraping
- treats resourceId as managed-resource identity
- has a preview/diff path now on this branch
- keeps human approval in the loop

### Current risky areas

The highest-risk areas are:

1. Flat export
   - subtotal groups and nested children are lost

2. Price drift
   - add-resource uses default pricing unless updated afterward

3. Time/pricing model drift
   - defaultTime and defaultPricingModelId are not copied

4. Hidden Flex fields
   - Swagger may not reveal the exact fields needed for subtotal/group creation

5. API call volume
   - matching should dedupe resource IDs and cache lookups

## Recommended Flex service layer

Create one internal module that owns all Flex behavior:

```txt
backend/app/flex/
  client.py          # low-level HTTP wrapper
  documents.py       # quote/document search, header reads, header updates
  line_items.py      # row-data, add-resource, update price, subtotal creation
  inventory.py       # managed-resource identity and inventory search
  schemas.py         # typed models for quote tree, line items, preview rows
```

The routes should call service functions and should not contain Flex-specific endpoint knowledge.

## Quote tree model

The app needs a tree model before subtotal export can be solved cleanly.

Suggested model:

```python
class QuoteLineNode(BaseModel):
    source_line_id: str | None = None
    parent_source_line_id: str | None = None
    destination_line_id: str | None = None
    line_type: str
    name: str
    quantity: float = 1
    resource_id: str | None = None
    matched_resource_id: str | None = None
    matched_name: str | None = None
    class_name: str | None = None
    price_each: float | None = None
    price_extended: float | None = None
    pricing_model_id: str | None = None
    pricing_model_name: str | None = None
    note: str | None = None
    sort_order: int = 0
    children: list[QuoteLineNode] = []
```

Key rule:
- Do not flatten until rendering a table.
- Export should walk the tree in order.

## Export order

Recommended export process:

1. Create quote header.
2. Set currency.
3. Copy quote-level fields:
   - plannedStartDate
   - plannedEndDate
   - defaultTime
   - defaultPricingModelId
   - clientId
   - locationId if relevant
4. Create subtotal/group nodes.
5. Add child resource/service items under the correct parent.
6. Apply quantity.
7. Apply priceEach and pricingModel overrides.
8. Re-fetch destination row-data.
9. Compare destination to preview.
10. Show export log.

## AI usage recommendation

AI should not replace deterministic matching.

Use this order:

1. resourceId exact lookup
2. cached resourceId lookup
3. deterministic inventory search
4. AI-ranked replacement suggestions
5. human approval

AI should only choose from candidates returned by Flex search.

Never allow the model to invent a Flex item ID.

Suggested AI output schema:

```python
class ReplacementSuggestion(BaseModel):
    inventory_id: str
    confidence: float
    reason: str

class ReplacementResult(BaseModel):
    suggestions: list[ReplacementSuggestion]
```

## Suggested MCP server

An MCP server makes sense, but not as the primary app.

It should expose safe, focused tools to AI assistants like Claude Code, Cursor, Copilot, or ChatGPT-style agents.

### Good MCP tools

```txt
flex_search_quotes(query)
flex_get_quote_summary(quote_id)
flex_get_quote_tree(quote_id)
flex_search_inventory(query)
flex_suggest_replacements(old_item, candidates)
flex_preview_quote_export(source_quote_id, decisions)
flex_validate_quote_export(payload)
```

### High-risk MCP tools

These should either be omitted at first or require explicit confirmation outside the model:

```txt
flex_create_quote(payload)
flex_update_quote_line_item(...)
flex_delete_line_item(...)
flex_finalize_export(...)
```

If write tools are included, they should:

- require a preview_id from a prior dry run
- require a human approval flag generated by the web UI
- log every action
- refuse destructive operations

## MCP architecture

Recommended structure:

```txt
quoter-motor/
  backend/
    app/
      flex/
        service.py
        schemas.py
      routes/
        quotes.py
  mcp-server/
    server.py
    pyproject.toml
```

The MCP server should import or call the same Flex service layer as the web app.

Do not duplicate Flex endpoint logic in the MCP server.

## MCP security notes

MCP servers expose tools to AI clients. That is powerful, but risky.

Security rules for this project:

1. Run MCP locally or over Tailscale only.
2. Do not expose it publicly through NPM or Cloudflare until auth is solved.
3. Keep write tools disabled at first.
4. Use a dedicated Flex API user with limited permissions.
5. Log every tool call.
6. Add rate limits.
7. Do not let prompts or quote text decide which endpoint to call.
8. Validate all tool inputs with Pydantic.

## Minimal MCP proof of concept

```python
from mcp.server.fastmcp import FastMCP
from app.flex.service import FlexService

mcp = FastMCP("Flex Rental MCP")

@mcp.tool()
async def flex_search_quotes(query: str) -> list[dict]:
    """Search Flex quotes by quote number, event name, or client text."""
    service = FlexService.from_env()
    return await service.search_quotes(query)

@mcp.tool()
async def flex_get_quote_summary(quote_id: str) -> dict:
    """Return quote header, item count, subtotal groups, and review warnings."""
    service = FlexService.from_env()
    return await service.get_quote_summary(quote_id)

@mcp.tool()
async def flex_search_inventory(query: str) -> list[dict]:
    """Search Flex inventory and service offerings."""
    service = FlexService.from_env()
    return await service.search_inventory(query)
```

## Recommended next development tasks

### Task 1: Capture Flex network calls

In Flex web UI, manually perform these actions while Chrome DevTools Network is open:

- create a subtotal/group line
- add an inventory item under a subtotal
- add a labor/service item under a subtotal
- change priceEach
- change pricingModel
- change quote defaultTime
- change quote defaultPricingModelId

Save the request URLs, methods, query params, and request bodies.

### Task 2: Build typed quote tree parsing

Replace `_flatten_line_items()` with:

- parse_quote_tree()
- flatten_quote_tree_for_review()
- preserve parent IDs and sort order

### Task 3: Add export preview IDs

Preview should produce a stable preview payload that create/export consumes.

The final create action should use the exact previewed payload.

### Task 4: AI replacement suggestions

Add OpenAI suggestions only for:

- missing resourceId
- deleted resourceId
- low confidence deterministic match

### Task 5: MCP read-only proof of concept

Start with read-only tools:

- search quotes
- get quote tree
- search inventory
- preview export

Only add write tools once the dry-run/export flow is trustworthy.

## Bottom line

An MCP server is a good idea, but it should not be the first place where quote export logic lives.

The core value should be a clean Flex service layer.

Then both the web app and MCP server can use it safely.
