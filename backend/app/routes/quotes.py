from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Any
import logging

from app.config import get_settings, Settings
from app.flex.client import FlexClient, FlexAPIError
from app.matching.engine import match_all_items

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])


# ------------------------------------------------------------------ deps

def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(
        base_url=settings.flex_base_url, api_key=settings.flex_api_key,
        
        
    )


def get_openai_client(settings: Settings = Depends(get_settings)):
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=settings.openai_api_key)


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


class CreateQuoteRequest(BaseModel):
    description: str
    client_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
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
        raise HTTPException(status_code=401, detail=str(e))
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
        raise HTTPException(status_code=401, detail=str(e))
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
    openai_client=Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    """
    Fetch a source quote and return AI-matched equivalents from current inventory.
    This is the heavy step — calls OpenAI once per line item.
    """
    try:
        document = await flex.get_document(body.source_quote_id)
        elements = await flex.get_document_elements(body.source_quote_id)
        inventory = await flex.get_all_elements()

        logger.info(
            "Matching %d items against %d inventory items",
            len(elements),
            len(inventory),
        )

        matches = await match_all_items(
            items=elements,
            inventory=inventory,
            openai_client=openai_client,
            model=settings.openai_model,
        )

        needs_review_count = sum(1 for m in matches if m["needs_review"])

        return {
            "document": document,
            "matches": matches,
            "inventory_size": len(inventory),
            "needs_review_count": needs_review_count,
        }

    except FlexAPIError as e:
        raise HTTPException(status_code=401, detail=str(e))
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
    try:
        doc_payload: dict[str, Any] = {"description": body.description}
        if body.client_id:
            doc_payload["clientId"] = body.client_id
        if body.start_date:
            doc_payload["startDateTime"] = body.start_date
        if body.end_date:
            doc_payload["endDateTime"] = body.end_date

        new_doc = await flex.create_document(doc_payload)
        new_doc_id = new_doc.get("id") or new_doc.get("documentId")

        if not new_doc_id:
            raise HTTPException(
                status_code=502,
                detail=f"Document created but no ID returned. Response: {new_doc}",
            )

        created_elements = []
        for i, item in enumerate(body.items):
            el_payload: dict[str, Any] = {
                "parentId": new_doc_id,
                "elementId": item.element_id,
                "quantity": item.quantity,
            }
            if item.unit_price is not None:
                el_payload["unitPrice"] = item.unit_price
            if item.note:
                el_payload["note"] = item.note
            if item.sort_order is not None:
                el_payload["sortOrder"] = item.sort_order
            else:
                el_payload["sortOrder"] = i

            try:
                result = await flex.create_document_element(el_payload)
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
        raise HTTPException(status_code=401, detail=str(e))
    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await flex.close()
