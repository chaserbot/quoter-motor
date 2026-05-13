import logging
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings, Settings
from app.flex.client import FlexClient, FlexAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(base_url=settings.flex_base_url, api_key=settings.flex_api_key)


@router.get("/search")
async def search_inventory(
    q: str,
    client: FlexClient = Depends(get_flex_client),
):
    """
    Search inventory models by name (used for manual override in the review UI).
    Requires at least 2 characters.
    """
    q = q.strip()
    if len(q) < 2:
        return {"items": [], "count": 0, "message": "Enter at least 2 characters to search"}
    try:
        items = await client.search_inventory(q)
        return {"items": items, "count": len(items)}
    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()
