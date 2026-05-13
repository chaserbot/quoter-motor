import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)


class FlexAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class FlexClient:
    def __init__(self, base_url: str, api_key: str):
        # base_url = https://clearlamp.flexrentalsolutions.com/f5
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "X-Auth-Token": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

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

    async def _paginate(self, path: str, params: dict, page_size: int = 100) -> list[dict]:
        results: list[dict] = []
        page = 0
        while True:
            data = await self._request("GET", path, params={**params, "size": page_size, "page": page})
            if isinstance(data, list):
                results.extend(data)
                if len(data) < page_size:
                    break
            elif isinstance(data, dict):
                batch = data.get("content", data.get("results", []))
                results.extend(batch)
                if data.get("last", True) or len(batch) < page_size:
                    break
            else:
                break
            page += 1
        return results

    # ---------------------------------------------------------- quotes

    async def search_documents(self, query: str) -> list[dict]:
        data = await self._request("GET", "/api/element/search", params={
            "searchString": query,
            "size": 20,
        })
        items = data.get("content", data) if isinstance(data, dict) else data
        return [x for x in items if x.get("definitionName") == "Quote"]

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

    async def get_all_elements(self) -> list[dict]:
        return await self._paginate("/api/element/search", {"searchString": ""})

    async def search_elements(self, query: str) -> list[dict]:
        data = await self._request("GET", "/api/element/search", params={
            "searchString": query,
            "size": 50,
        })
        return data.get("content", data) if isinstance(data, dict) else data

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
            data = await self._request("GET", "/api/element/search", params={"searchString": "test", "size": 1})
            return {"ok": True, "sample": data}
        except FlexAPIError as e:
            return {"ok": False, "error": str(e), "status_code": e.status_code, "body": e.body}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def close(self):
        await self._http.aclose()
