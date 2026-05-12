import httpx
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Flex returns different field names depending on version / config.
# We try each in order and take the first hit.
_TOKEN_FIELDS = ("id", "token", "accessToken", "sessionToken")
_AUTH_HEADERS = ("X-Auth-Token", "Authorization")  # We'll try X-Auth-Token first


class FlexAuthError(Exception):
    pass


class FlexAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class FlexClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._auth_header: str = "X-Auth-Token"
        self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    # ------------------------------------------------------------------ auth

    async def _authenticate(self) -> str:
        payload = {"username": self.username, "password": self.password}
        try:
            resp = await self._http.post(
                f"{self.base_url}/authenticate",
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        except httpx.ConnectError as e:
            raise FlexAuthError(f"Cannot reach Flex API at {self.base_url}: {e}") from e

        if resp.status_code in (401, 403):
            raise FlexAuthError("Flex authentication failed — check FLEX_USERNAME and FLEX_PASSWORD")

        if not resp.is_success:
            raise FlexAuthError(
                f"Flex authenticate returned {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        token = None
        for field in _TOKEN_FIELDS:
            if data.get(field):
                token = data[field]
                break

        if not token:
            raise FlexAuthError(
                f"Could not find token in auth response. Keys returned: {list(data.keys())}"
            )

        logger.info("Flex authentication successful")
        return token

    async def _get_token(self) -> str:
        if not self._token or (
            self._token_expires and datetime.now() >= self._token_expires
        ):
            self._token = await self._authenticate()
            # Flex tokens typically last 1 hour; refresh 5 min early to be safe
            self._token_expires = datetime.now() + timedelta(minutes=55)
        return self._token

    # --------------------------------------------------------------- requests

    async def _request(
        self,
        method: str,
        path: str,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> Any:
        token = await self._get_token()
        headers = kwargs.pop("headers", {})
        headers[self._auth_header] = token
        headers["Accept"] = "application/json"

        url = f"{self.base_url}{path}"
        resp = await self._http.request(method, url, headers=headers, **kwargs)

        if resp.status_code == 401 and retry_auth:
            # Token may have expired server-side; force refresh once
            self._token = None
            token = await self._get_token()
            headers[self._auth_header] = token
            resp = await self._http.request(method, url, headers=headers, **kwargs)

        if not resp.is_success:
            raise FlexAPIError(
                f"Flex API {method} {path} returned {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        # Some endpoints return empty body on success
        if not resp.content:
            return {}

        return resp.json()

    # ------------------------------------------------------------ pagination

    async def _paginate(self, path: str, params: dict, page_size: int = 200) -> list[dict]:
        """Fetch all pages from a Flex list endpoint."""
        results: list[dict] = []
        offset = 0
        while True:
            params = {**params, "limit": page_size, "offset": offset}
            data = await self._request("GET", path, params=params)

            # Flex can return a list or an object with a results key
            if isinstance(data, list):
                batch = data
            elif isinstance(data, dict):
                batch = data.get("results", data.get("content", []))
            else:
                break

            results.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size

        return results

    # --------------------------------------------------------- document API

    async def get_document(self, doc_id: str) -> dict:
        return await self._request("GET", f"/document/{doc_id}")

    async def search_documents(self, document_number: str) -> list[dict]:
        """Search for a document by its human-readable quote number."""
        return await self._paginate(
            "/document",
            {"filter": f"documentNumber::=={document_number}"},
        )

    async def get_document_elements(self, document_id: str) -> list[dict]:
        """Return all line items for a document."""
        return await self._paginate(
            "/documentElement",
            {"filter": f"parentId::=={document_id}"},
        )

    # --------------------------------------------------------- inventory API

    async def get_all_elements(self) -> list[dict]:
        """Return all active inventory elements (the catalog)."""
        return await self._paginate(
            "/element",
            {"filter": "active::==true"},
        )

    async def get_element(self, element_id: str) -> dict:
        return await self._request("GET", f"/element/{element_id}")

    # --------------------------------------------------- document creation

    async def create_document(self, payload: dict) -> dict:
        return await self._request("POST", "/document", json=payload)

    async def create_document_element(self, payload: dict) -> dict:
        return await self._request("POST", "/documentElement", json=payload)

    # ---------------------------------------------------- connection check

    async def test_connection(self) -> dict:
        """Verify credentials and return basic info. Used by the UI health check."""
        try:
            token = await self._get_token()
            return {"ok": True, "token_preview": token[:8] + "…"}
        except FlexAuthError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def close(self):
        await self._http.aclose()
