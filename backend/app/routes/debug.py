"""
Debug / health-check routes. Helps verify Flex connectivity and API structure
without needing to match a real quote first.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings, Settings
from app.flex.client import FlexClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["debug"])


def get_flex_client(settings: Settings = Depends(get_settings)) -> FlexClient:
    return FlexClient(
        base_url=settings.flex_base_url, api_key=settings.flex_api_key,
        
        
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": "quoter-motor"}


@router.get("/flex-connection")
async def flex_connection(client: FlexClient = Depends(get_flex_client)):
    """Test Flex credentials and return the first 3 inventory items as a sanity check."""
    result = await client.test_connection()
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["error"])

    # Fetch a tiny slice of inventory to confirm read access
    try:
        sample = await client._request("GET", "/element", params={"limit": 3, "offset": 0})
    except Exception as e:
        await client.close()
        return {**result, "inventory_sample": None, "inventory_error": str(e)}

    await client.close()
    return {
        **result,
        "inventory_sample": sample if isinstance(sample, list) else sample.get("results", sample),
    }


@router.get("/flex-raw")
async def flex_raw(
    path: str,
    client: FlexClient = Depends(get_flex_client),
):
    """
    Make an authenticated GET to any Flex API path and return the raw response.
    Useful for exploring the API structure. Example: path=/element?limit=2
    """
    if not path.startswith("/"):
        path = "/" + path
    try:
        data = await client._request("GET", path)
        return {"path": path, "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        await client.close()
