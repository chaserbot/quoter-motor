import httpx
import logging
import time
import asyncio
from typing import Any

logger = logging.getLogger(__name__)

QUOTE_DEFINITION_IDS = {
    "9bfb850c-b117-11df-b8d5-00e08175e43e",  # Quote
    "6f36f740-a565-11e3-a128-00259000d29a",  # Sales Quote
    "a29f8b12-d210-11e1-bba1-00e08175e43e",  # Quick Quote
}

# Element types that are NOT inventory (quotes, manifests, folders, etc.)
NON_INVENTORY_DEFINITIONS = {
    "9bfb850c-b117-11df-b8d5-00e08175e43e",  # Quote
    "6f36f740-a565-11e3-a128-00259000d29a",  # Sales Quote
    "a29f8b12-d210-11e1-bba1-00e08175e43e",  # Quick Quote
    "358f312c-b051-11df-b8d5-00e08175e43e",  # Event Folder
    "d256daec-b055-11df-b8d5-00e08175e43e",  # Invoice
    "9945d54c-af32-11df-b8d5-00e08175e43e",  # Manifest
    "a220432c-af33-11df-b8d5-00e08175e43e",  # Pull Sheet
    "ebd0831c-c87b-11e0-a8de-00e08175e43e",  # Received Payment
    "c2eaed0c-b0bc-11df-b8d5-00e08175e43e",  # Rental PO
    "f6e70edc-f42d-11e0-a8de-00e08175e43e",  # Labor PO
    "f1fa534c-b0b4-11df-b8d5-00e08175e43e",  # Purchase PO
    "1720ed80-8d20-11e2-b07f-00e08175e43e",  # Credit Memo
    "566d32e0-1a1e-11e0-a472-00e08175e43e",  # Expense Sheet
    "253878cc-af31-11df-b8d5-00e08175e43e",  # Crew Call
    "3787806c-af2d-11df-b8d5-00e08175e43e",  # Document
    "c116e410-cc36-11e3-b7de-00259000d29a",  # Task
    "e8cda460-741a-11e1-9988-00e08175e43e",  # Transfer Manifest
    "4690b980-7451-11e1-9988-00e08175e43e",  # Transfer Order
    "a0134a1c-75ac-11e0-a8de-00e08175e43e",  # Purchase PO Intake Manifest
    "d2c66a5c-75ac-11e0-a8de-00e08175e43e",  # Subrental Intake Manifest
    "f8041b5c-75ac-11e0-a8de-00e08175e43e",  # Subrental Return Manifest
}


class FlexAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ---------------------------------------------------------------------------
# Module-level cache shared across all request lifetimes
# ---------------------------------------------------------------------------
_cache: dict = {
    "all_elements": None,   # every element from Flex
    "quotes": None,         # filtered to quote types only
    "inventory": None,      # filtered to non-document types (actual gear/labor)
    "fetched_at": 0.0,
    "loading": False,
}


class FlexClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "X-Auth-Token": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    # ---------------------------------------------------------------- core

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp = await self._http.request(method, url, headers=headers, **kwargs)
        if not resp.is_success:
            raise FlexAPIError(
                f"Flex API {method} {path} → {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
        return resp.json() if resp.content else {}

    # ---------------------------------------------------------------- bulk load

    async def _load_all_elements(self) -> list[dict]:
        """Fetch every element from Flex in large pages (~10 API calls)."""
        results: list[dict] = []
        page = 0
        page_size = 1000
        while True:
            data = await self._request("GET", "/api/element/search", params={
                "searchString": "",
                "size": page_size,
                "page": page,
            })
            batch = data.get("content", []) if isinstance(data, dict) else data
            results.extend(batch)
            is_last = data.get("last", True) if isinstance(data, dict) else True
            if is_last or len(batch) < page_size:
                break
            page += 1
        logger.info("Loaded %d total elements from Flex", len(results))
        return results

    async def warm_cache(self, ttl: int = 300) -> None:
        """Load and split all elements into quotes vs inventory. Cached for ttl seconds."""
        if _cache["loading"]:
            return
        now = time.time()
        if _cache["all_elements"] is not None and now - _cache["fetched_at"] < ttl:
            return

        _cache["loading"] = True
        try:
            all_elements = await self._load_all_elements()
            quotes = []
            inventory = []
            for el in all_elements:
                def_id = el.get("definitionId", "")
                def_name = el.get("definitionName", "")
                if def_id in QUOTE_DEFINITION_IDS or def_name in ("Quote", "Sales Quote", "Quick Quote"):
                    quotes.append(el)
                elif def_id not in NON_INVENTORY_DEFINITIONS and def_name not in NON_INVENTORY_DEFINITIONS:
                    inventory.append(el)

            _cache["all_elements"] = all_elements
            _cache["quotes"] = quotes
            _cache["inventory"] = inventory
            _cache["fetched_at"] = time.time()
            logger.info("Cache warmed: %d quotes, %d inventory items", len(quotes), len(inventory))
        finally:
            _cache["loading"] = False

    # ---------------------------------------------------------- quotes

    def _search_cached(self, items: list[dict], query: str) -> list[dict]:
        q = query.lower().strip()
        if not q:
            return items
        results = []
        for x in items:
            num = (x.get("documentNumber") or x.get("number") or "").lower()
            name = (x.get("name") or "").lower()
            parent = (x.get("parentName") or "").lower()
            if q in num or q in name or q in parent:
                results.append(x)
        return results

    async def search_documents(self, query: str, ttl: int = 300) -> list[dict]:
        await self.warm_cache(ttl)
        return self._search_cached(_cache["quotes"] or [], query)[:50]

    async def get_document(self, doc_id: str) -> dict:
        return await self._request("GET", f"/api/element/{doc_id}/header-data")

    async def get_document_elements(self, document_id: str) -> list[dict]:
        data = await self._request(
            "GET",
            f"/api/financial-document-line-item/{document_id}/row-data/",
            params={"codeList": "RESOURCE,LABOR,MISC"},
        )
        if isinstance(data, list):
            return data
        return data.get("content", data.get("rows", data.get("lineItems", [])))

    # ---------------------------------------------------------- inventory

    async def get_all_elements(self, ttl: int = 300) -> list[dict]:
        await self.warm_cache(ttl)
        return _cache["inventory"] or []

    async def search_elements(self, query: str, ttl: int = 300) -> list[dict]:
        await self.warm_cache(ttl)
        return self._search_cached(_cache["inventory"] or [], query)[:50]

    # ---------------------------------------------------------- creation

    async def create_document(self, payload: dict) -> dict:
        return await self._request("POST", "/api/element", json=payload)

    async def add_line_item(self, document_id: str, resource_id: str, payload: dict) -> dict:
        return await self._request(
            "POST",
            f"/api/financial-document-line-item/{document_id}/add-resource/{resource_id}",
            json=payload,
        )

    # ---------------------------------------------------------- health

    async def test_connection(self) -> dict:
        try:
            data = await self._request("GET", "/api/element/search", params={"searchString": "", "size": 1})
            total = data.get("totalElements", "?") if isinstance(data, dict) else "?"
            return {"ok": True, "total_elements": total}
        except FlexAPIError as e:
            return {"ok": False, "error": str(e), "status_code": e.status_code, "body": e.body}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def close(self):
        await self._http.aclose()
