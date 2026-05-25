import httpx
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

QUOTE_DEFINITION_IDS = {
    "9bfb850c-b117-11df-b8d5-00e08175e43e",  # Quote
    "6f36f740-a565-11e3-a128-00259000d29a",  # Sales Quote
    "a29f8b12-d210-11e1-bba1-00e08175e43e",  # Quick Quote
}

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
# Module-level cache for quotes (element/search). Inventory uses live API calls.
# ---------------------------------------------------------------------------
_cache: dict = {
    "quotes": None,
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

    # ---------------------------------------------------------------- quote cache

    async def _load_all_elements(self) -> list[dict]:
        """Fetch all financial elements (quotes, invoices, events) from Flex."""
        results: list[dict] = []
        page = 0
        page_size = 1000
        while True:
            data = await self._request("GET", "/api/element/search", params={
                "searchText": "",
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
        """Load and cache quotes from element/search. Cached for ttl seconds."""
        if _cache["loading"]:
            return
        now = time.time()
        if _cache["quotes"] is not None and now - _cache["fetched_at"] < ttl:
            return

        _cache["loading"] = True
        try:
            all_elements = await self._load_all_elements()
            quotes = []
            for el in all_elements:
                def_id = el.get("definitionId") or ""
                def_name = el.get("definitionName") or ""
                if def_id in QUOTE_DEFINITION_IDS or def_name in ("Quote", "Sales Quote", "Quick Quote"):
                    quotes.append(el)

            _cache["quotes"] = quotes
            _cache["fetched_at"] = time.time()
            logger.info("Cache warmed: %d quotes", len(quotes))
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
        results = self._search_cached(_cache["quotes"] or [], query)
        seen: set[str] = set()
        unique = []
        for r in results:
            rid = r.get("id")
            if rid and rid not in seen:
                seen.add(rid)
                unique.append(r)
        return unique[:50]

    async def get_document(self, doc_id: str) -> dict:
        HEADER_CODES = (
            "name,documentNumber,plannedStartDate,plannedEndDate,statusId,clientId,"
            "clientCompany,totalPrice,locationId,defaultTime,defaultPricingModelId"
        )
        raw = await self._request(
            "GET",
            f"/api/element/{doc_id}/header-data",
            params={"codeList": HEADER_CODES},
        )
        return self._normalize_document(doc_id, raw)

    def _normalize_document(self, doc_id: str, raw: dict) -> dict:
        """Flatten Flex's {fieldType, data} envelope into a plain dict."""
        def extract(v):
            if isinstance(v, dict) and "data" in v:
                return v["data"]
            return v

        result: dict = {"id": doc_id}
        for key, value in raw.items():
            result[key] = extract(value)

        client = result.get("clientId")
        if isinstance(client, dict):
            result["clientName"] = client.get("preferredDisplayString") or client.get("name")
            result["clientId"] = client.get("id")

        result.setdefault("description", result.pop("name", None))
        result.setdefault("startDateTime", result.pop("plannedStartDate", None))
        result.setdefault("endDateTime", result.pop("plannedEndDate", None))

        return result

    async def get_document_elements(self, document_id: str) -> list[dict]:
        data = await self._request(
            "GET",
            f"/api/financial-document-line-item/{document_id}/row-data/",
            params=[
                ("codeList", "type"),
                ("codeList", "quantity"),
                ("codeList", "name"),
                ("codeList", "note"),
                ("codeList", "priceEach"),
                ("codeList", "priceExtended"),
                ("codeList", "pricingModel"),
                ("codeList", "resourceId"),
                ("node", "root"),
            ],
        )
        if isinstance(data, list):
            rows = data
        else:
            rows = data.get("content", data.get("rows", data.get("lineItems", data.get("rowData", []))))
        logger.info("row-data: %d top-level rows", len(rows))
        if rows:
            return self._flatten_line_items(rows)
        return []

    def _flatten_line_items(self, rows: list[dict]) -> list[dict]:
        """Recursively flatten subtotal tree into a flat list of resource/labor items."""
        result = []
        for row in rows:
            children = row.get("children") or []
            if children:
                result.extend(self._flatten_line_items(children))
            elif row.get("resourceId") or row.get("lineItemType") in ("resource", "labor", "misc"):
                result.append(row)
        return result

    # ---------------------------------------------------------- inventory model lookup

    async def get_inventory_model(self, resource_id: str) -> dict | None:
        """
        Look up a single inventory model by ID via managed-resource/identity.
        This is the correct endpoint for resolving resourceId values from quote line items.
        """
        try:
            data = await self._request(
                "GET",
                f"/api/managed-resource/{resource_id}/identity",
            )
            if data and data.get("name") and not data.get("deleted"):
                return data
            return None
        except FlexAPIError as e:
            if e.status_code in (404, 500):
                return None
            raise

    async def search_inventory(self, query: str) -> list[dict]:
        """
        Search inventory models via /api/inventory-model/search.
        Requires at least 2 characters.
        """
        q = query.strip()
        if len(q) < 2:
            return []
        data = await self._request(
            "GET",
            "/api/inventory-model/search",
            params={"searchText": q, "size": 50},
        )
        items = data.get("content", data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    # ---------------------------------------------------------- creation

    DEFAULT_CURRENCY_ID = "911e3d4c-aedc-11df-b8d5-00e08175e43e"  # US Dollar

    # Map managed-resource className → managedResourceLineItemType query param
    CLASS_TO_LINE_ITEM_TYPE = {
        "INVENTORY_MODEL": "inventory-model",
        "SERVICE_OFFERING": "service-offering",
        "SERIAL_UNIT": "serial-unit",
        "CONTACT": "contact",
    }

    async def create_document(self, payload: dict) -> dict:
        doc = await self._request("POST", "/api/element", json=payload)
        doc_id = doc.get("elementId") or doc.get("id")
        if doc_id:
            await self.update_header_field(doc_id, "currencyId", self.DEFAULT_CURRENCY_ID)
        return doc

    async def update_header_field(self, document_id: str, field_type: str, payload_value: Any) -> dict:
        return await self._request(
            "POST",
            f"/api/element/{document_id}/header-update",
            json={"fieldType": field_type, "payloadValue": payload_value},
        )

    def get_primary_line_item_id(self, add_resource_response: dict) -> str | None:
        """Return the main line item ID from Flex's add-resource response."""
        if not isinstance(add_resource_response, dict):
            return None
        for key in ("affectedRootLineIds", "addedResourceLineIds"):
            value = add_resource_response.get(key)
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str) and value:
                return value
        return None

    async def update_line_item_field(self, line_item_id: str, field_type: str, payload_value: Any) -> dict:
        return await self._request(
            "PUT",
            f"/api/line-item/{line_item_id}/update",
            json={"fieldType": field_type, "payloadValue": payload_value},
        )

    async def add_line_item(
        self,
        document_id: str,
        resource_id: str,
        quantity: float,
        class_name: str = "INVENTORY_MODEL",
    ) -> dict:
        line_item_type = self.CLASS_TO_LINE_ITEM_TYPE.get(class_name, "inventory-model")
        return await self._request(
            "POST",
            f"/api/line-item/{document_id}/add-resource/{resource_id}",
            params={
                "resourceParentId": document_id,
                "managedResourceLineItemType": line_item_type,
                "quantity": quantity,
            },
        )

    # ---------------------------------------------------------- health

    async def test_connection(self) -> dict:
        try:
            data = await self._request("GET", "/api/element/search", params={"searchText": "", "size": 1})
            total = data.get("totalElements", "?") if isinstance(data, dict) else "?"
            return {"ok": True, "total_elements": total}
        except FlexAPIError as e:
            return {"ok": False, "error": str(e), "status_code": e.status_code, "body": e.body}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def close(self):
        await self._http.aclose()
