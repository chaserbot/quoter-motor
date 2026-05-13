from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import logging
import asyncio

from app.config import get_settings, Settings
from app.flex.client import FlexClient, FlexAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])


def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(base_url=settings.flex_base_url, api_key=settings.flex_api_key)


class SourceQuoteResponse(BaseModel):
    document: dict[str, Any]
    elements: list[dict[str, Any]]
    element_count: int


class MatchRequest(BaseModel):
    source_quote_id: str


class ApprovedItem(BaseModel):
    element_id: str
    quantity: float
    unit_price: Optional[float] = None
    note: Optional[str] = None
    sort_order: Optional[int] = None
    class_name: Optional[str] = None
    old_item: Optional[dict[str, Any]] = None
    approved_name: Optional[str] = None


class CreateQuoteRequest(BaseModel):
    description: str
    client_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    items: list[ApprovedItem]


def build_preview(body: CreateQuoteRequest) -> dict[str, Any]:
    issues = []
    diff = []

    old_total = 0.0
    new_total = 0.0

    for i, item in enumerate(body.items):
        old_item = item.old_item or {}

        old_name = (
            old_item.get("name")
            or old_item.get("elementName")
            or old_item.get("description")
            or "Unknown"
        )

        qty = item.quantity or 0
        old_unit_price = float(old_item.get("priceEach") or item.unit_price or 0)
        new_unit_price = float(item.unit_price or old_unit_price or 0)

        old_extended = old_unit_price * qty
        new_extended = new_unit_price * qty
        delta = new_extended - old_extended

        old_total += old_extended
        new_total += new_extended

        if qty <= 0:
            issues.append({
                "level": "warning",
                "message": f"Item {i + 1} has quantity 0",
                "item_index": i,
            })

        if not item.element_id:
            issues.append({
                "level": "error",
                "message": f"Item {i + 1} is missing a replacement item",
                "item_index": i,
            })

        if abs(delta) > 250:
            issues.append({
                "level": "info",
                "message": f"Large pricing delta detected on '{old_name}'",
                "item_index": i,
            })

        diff.append({
            "index": i,
            "old_name": old_name,
            "new_name": item.approved_name or old_name,
            "quantity": qty,
            "old_unit_price": old_unit_price,
            "new_unit_price": new_unit_price,
            "old_extended": old_extended,
            "new_extended": new_extended,
            "delta": delta,
            "note": item.note,
        })

    planned_operations = [
        f"Create Flex quote '{body.description}'",
        "Apply quote currency",
        f"Add {len(body.items)} approved line items",
        "Apply quantity overrides",
        "Validate pricing and subtotal structure",
        "Finalize export to Flex",
    ]

    return {
        "valid": not any(i["level"] == "error" for i in issues),
        "issues": issues,
        "diff": diff,
        "planned_operations": planned_operations,
        "totals": {
            "old_total": round(old_total, 2),
            "new_total": round(new_total, 2),
            "delta": round(new_total - old_total, 2),
        },
    }


@router.get("/search")
async def search_quotes(
    q: str,
    client: FlexClient = Depends(get_flex_client),
):
    try:
        results = await client.search_documents(q)
        return {"results": results}
    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()


@router.get("/{doc_id}")
async def get_source_quote(
    doc_id: str,
    client: FlexClient = Depends(get_flex_client),
) -> SourceQuoteResponse:
    try:
        document = await client.get_document(doc_id)
        elements = await client.get_document_elements(doc_id)
        return SourceQuoteResponse(
            document=document,
            elements=elements,
            element_count=len(elements),
        )
    except FlexAPIError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Quote {doc_id} not found")
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()


@router.post("/match")
async def match_quote_items(
    body: MatchRequest,
    flex: FlexClient = Depends(get_flex_client),
):
    try:
        document = await flex.get_document(body.source_quote_id)
        elements = await flex.get_document_elements(body.source_quote_id)

        logger.info("Resolving %d line items by resourceId", len(elements))

        resource_cache: dict[str, dict | None] = {}

        async def resolve(item: dict) -> dict:
            resource_id = item.get("resourceId")
            if not resource_id:
                return {
                    "old_item": item,
                    "match": None,
                    "confidence": 0.0,
                    "reason": "No resourceId on line item",
                    "alternatives": [],
                    "needs_review": True,
                }

            if resource_id not in resource_cache:
                resource_cache[resource_id] = await flex.get_inventory_model(resource_id)

            current = resource_cache[resource_id]

            if current:
                return {
                    "old_item": item,
                    "match": current,
                    "confidence": 1.0,
                    "reason": "Item found in current inventory",
                    "alternatives": [],
                    "needs_review": False,
                }

            return {
                "old_item": item,
                "match": None,
                "confidence": 0.0,
                "reason": "Item no longer in inventory — select replacement manually",
                "alternatives": [],
                "needs_review": True,
            }

        matches = await asyncio.gather(*[resolve(el) for el in elements])
        matched = sum(1 for m in matches if m["match"])
        logger.info("Resolved %d / %d items", matched, len(elements))

        return {
            "document": document,
            "matches": list(matches),
            "needs_review_count": sum(1 for m in matches if m["needs_review"]),
        }

    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await flex.close()


@router.post("/preview")
async def preview_quote(body: CreateQuoteRequest):
    return build_preview(body)


@router.post("/create")
async def create_quote(
    body: CreateQuoteRequest,
    flex: FlexClient = Depends(get_flex_client),
):
    QUOTE_DEFINITION_ID = "9bfb850c-b117-11df-b8d5-00e08175e43e"

    def to_flex_datetime(date_str: str) -> str:
        return f"{date_str}T00:00:00" if date_str and "T" not in date_str else date_str

    try:
        preview = build_preview(body)

        if not preview["valid"]:
            raise HTTPException(status_code=400, detail=preview)

        doc_payload: dict[str, Any] = {
            "name": body.description,
            "definitionId": QUOTE_DEFINITION_ID,
        }

        if body.client_id:
            doc_payload["clientId"] = body.client_id
        if body.start_date:
            doc_payload["plannedStartDate"] = to_flex_datetime(body.start_date)
        if body.end_date:
            doc_payload["plannedEndDate"] = to_flex_datetime(body.end_date)

        new_doc = await flex.create_document(doc_payload)
        new_doc_id = new_doc.get("elementId") or new_doc.get("id") or new_doc.get("documentId")

        if not new_doc_id:
            raise HTTPException(
                status_code=502,
                detail=f"Document created but no ID returned. Response: {new_doc}",
            )

        created_elements = []

        for item in body.items:
            try:
                result = await flex.add_line_item(
                    new_doc_id,
                    item.element_id,
                    quantity=item.quantity,
                    class_name=item.class_name or "INVENTORY_MODEL",
                )

                created_elements.append({"ok": True, "element": result})

            except FlexAPIError as e:
                logger.warning(
                    "Failed to add element %s to doc %s: %s",
                    item.element_id,
                    new_doc_id,
                    e,
                )

                created_elements.append(
                    {"ok": False, "element_id": item.element_id, "error": str(e)}
                )

        failed = [e for e in created_elements if not e["ok"]]

        return {
            "document": new_doc,
            "document_id": new_doc_id,
            "document_number": new_doc.get("documentNumber"),
            "items_created": len(created_elements) - len(failed),
            "items_failed": len(failed),
            "failures": failed,
        }

    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await flex.close()
