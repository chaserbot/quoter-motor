# Export Refactor Plan

## Primary architectural issue

The current export flow intentionally flattens the source quote tree before creating the new quote.

This causes:
- subtotal groups to disappear
- nested line items to disappear
- sort order inconsistencies
- incorrect subtotal math
- pricing model drift
- loss of parent-child relationships

Current flattening happens in:

- backend/app/flex/client.py
  - `_flatten_line_items()`

Current quote creation happens in:

- backend/app/routes/quotes.py
  - `create_quote()`

## Recommended direction

Instead of flattening the quote into a simple list, preserve the original Flex quote structure as a tree.

Suggested model:

```python
class QuoteNode:
    id: str
    parent_id: str | None
    line_type: str
    name: str
    quantity: float
    resource_id: str | None
    price_each: float | None
    price_extended: float | None
    pricing_model: str | None
    sort_order: int
    children: list[QuoteNode]
```

## Required export fixes

### 1. Preserve subtotal groups

The source quote contains nested subtotal/group rows.

Current behavior:
- children are recursively flattened
- subtotal rows are discarded

Desired behavior:
- preserve group rows
- create subtotal/group rows in the destination quote first
- add child items underneath the correct parent

Likely Flex API requirement:
- parentLineItemId
- or parent resource line id

Swagger should be searched for:
- subtotal
- parentLineItemId
- line-item
- financial-document-line-item

## 2. Preserve original prices

Current behavior:
- add-resource uses catalog/default pricing
- negotiated quote pricing is lost

Desired behavior:
- after add-resource returns root line item IDs:
  - update priceEach
  - update pricingModel
  - possibly update priceExtended if supported

Swagger search terms:
- priceEach
- pricingModel
- update

## 3. Preserve quote-level pricing settings

Currently missing:
- defaultTime
- defaultPricingModelId

These affect rental duration calculations.

Desired behavior:
- read from source quote header
- apply to destination quote header immediately after create

## 4. Reduce Flex API calls

Current behavior:
- one managed-resource lookup per line item
- duplicate line items trigger duplicate API calls

Desired behavior:
- dedupe resource IDs before lookup
- cache lookups for request lifetime

Pseudo:

```python
resource_cache = {}

if resource_id not in resource_cache:
    resource_cache[resource_id] = await flex.get_inventory_model(resource_id)
```

## 5. Remove bandaid complexity

Potential cleanup candidates:

- remove unused NON_INVENTORY_DEFINITIONS logic
- remove unused matching-engine complexity if direct resourceId matching remains primary
- remove fields that are never applied during export
- centralize Flex field names/constants into one module

## 6. Frontend improvements

Current frontend loses important export metadata.

Review state should preserve:
- parent relationships
- subtotal structure
- original pricing
- pricing model
- notes
- sort order

The frontend should display hierarchy visually instead of only a flat list.

## 7. Suggested next implementation order

1. Preserve source quote tree
2. Export nested structure correctly
3. Copy pricing model + defaultTime
4. Copy priceEach
5. Add subtotal recreation
6. UI hierarchy improvements
7. Performance cleanup

## Notes

The current repo is actually fairly clean overall for a rapidly iterated Claude Code project.

The main issue is not readability.
The main issue is that the data model became flat too early in the pipeline.

Once the tree structure is preserved, most remaining export issues become much easier to solve.
