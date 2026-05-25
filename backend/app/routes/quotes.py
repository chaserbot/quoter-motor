from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import logging
import asyncio

from app.config import get_settings, Settings
from app.flex.client import FlexClient, FlexAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])


# ------------------------------------------------------------------ deps

def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(base_url=settings.flex_base_url, api_key=settings.flex_api_key)


# ---------------------------------------------------------------- schemas

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
    class_name: Optional[str] = None  # INVENTORY_MODEL, SERVICE_OFFERING, etc.


class CreateQuoteRequest(BaseModel):
    description: str
    client_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    default_time: Optional[Any] = None
    default_pricing_model_id: Optional[str] = None
    items: list[ApprovedItem]


# --------------------------------------------------------------- routes

@router.get("/search")
async def search_quotes(
    q: str,
    client: FlexClient = Depends(get_flex_client),
):
    """Search for Flex documents by document number or description."""
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
    """Fetch a single Flex document and all its line items."""
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
    """
    Fetch a source quote and resolve each line item by its resourceId via
    managed-resource/identity. Items that still exist in inventory are matched
    directly. Items that have been removed need manual selection.
    """
    try:
        document = await flex.get_document(body.source_quote_id)
        elements = await flex.get_document_elements(body.source_quote_id)

        logger.info("Resolving %d line items by resourceId", len(elements))

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
            current = await flex.get_inventory_model(resource_id)
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


@router.post("/create")
async def create_quote(
    body: CreateQuoteRequest,
    flex: FlexClient = Depends(get_flex_client),
):
    """
    Create a new Flex document and populate it with the approved items.
    Returns the new document id and document number.
    """
    QUOTE_DEFINITION_ID = "9bfb850c-b117-11df-b8d5-00e08175e43e"

    def to_flex_datetime(date_str: str) -> str:
        """Convert YYYY-MM-DD to Flex's expected date-time format."""
        return f"{date_str}T00:00:00" if date_str and "T" not in date_str else date_str

    try:
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

        if body.default_time is not None:
            try:
                await flex.update_header_field(new_doc_id, "defaultTime", body.default_time)
            except FlexAPIError as e:
                logger.warning("Failed to update defaultTime on doc %s: %s", new_doc_id, e)
        if body.default_pricing_model_id:
            try:
                await flex.update_header_field(
                    new_doc_id, "defaultPricingModelId", body.default_pricing_model_id
                )
            except FlexAPIError as e:
                logger.warning("Failed to update defaultPricingModelId on doc %s: %s", new_doc_id, e)

        created_elements = []
        for i, item in enumerate(body.items):
            try:
                result = await flex.add_line_item(
                    new_doc_id,
                    item.element_id,
                    quantity=item.quantity,
                    class_name=item.class_name or "INVENTORY_MODEL",
                )
                # Item was added — now apply optional field overrides.
                # These are best-effort: if the ID is missing we log and move on
                # rather than marking the (already-added) item as failed.
                if item.unit_price is not None or item.note:
                    line_item_id = flex.get_primary_line_item_id(result)
                    if not line_item_id:
                        logger.warning(
                            "Added element %s but Flex returned no root line item ID — "
                            "price/note not copied",
                            item.element_id,
                        )
                    else:
                        try:
                            if item.unit_price is not None:
                                await flex.update_line_item_field(
                                    line_item_id, "priceEach", item.unit_price
                                )
                            if item.note:
                                await flex.update_line_item_field(
                                    line_item_id, "note", item.note
                                )
                        except FlexAPIError as e:
                            logger.warning(
                                "Added element %s but failed to update price/note: %s",
                                item.element_id,
                                e,
                            )
                created_elements.append({"ok": True, "element": result})
            except FlexAPIError as e:
                logger.warning(
                    "Failed to add or update element %s on doc %s: %s",
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
