import time
import logging
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings, Settings
from app.flex.client import FlexClient, FlexAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["inventory"])

# Simple in-process cache so we don't hammer Flex for every match request
_cache: dict = {"data": None, "fetched_at": 0.0}


def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(
        base_url=settings.flex_base_url, api_key=settings.flex_api_key,
        
        
    )


@router.get("/")
async def list_inventory(
    force_refresh: bool = False,
    client: FlexClient = Depends(get_flex_client),
    settings: Settings = Depends(get_settings),
):
    """Return the full active inventory, cached for inventory_cache_ttl seconds."""
    now = time.time()
    if (
        not force_refresh
        and _cache["data"] is not None
        and now - _cache["fetched_at"] < settings.inventory_cache_ttl
    ):
        return {
            "items": _cache["data"],
            "count": len(_cache["data"]),
            "cached": True,
            "cache_age_seconds": int(now - _cache["fetched_at"]),
        }

    try:
        items = await client.get_all_elements()
        _cache["data"] = items
        _cache["fetched_at"] = now
        return {"items": items, "count": len(items), "cached": False, "cache_age_seconds": 0}
    except FlexAPIError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except FlexAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()


@router.get("/search")
async def search_inventory(
    q: str,
    client: FlexClient = Depends(get_flex_client),
    settings: Settings = Depends(get_settings),
):
    """Search inventory by name substring (used for manual override in the review UI)."""
    now = time.time()
    if _cache["data"] is None or now - _cache["fetched_at"] >= settings.inventory_cache_ttl:
        try:
            items = await client.get_all_elements()
            _cache["data"] = items
            _cache["fetched_at"] = now
        except (FlexAPIError) as e:
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            await client.close()

    q_lower = q.lower()
    matches = [
        item for item in _cache["data"]
        if q_lower in (item.get("name") or "").lower()
        or q_lower in (item.get("description") or "").lower()
    ]
    return {"items": matches[:50], "count": len(matches)}
