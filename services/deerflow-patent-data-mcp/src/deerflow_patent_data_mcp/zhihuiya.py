"""Minimal Wisdom芽 client for the verified M1A endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class ZhihuiyaClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._settings.zhihuiya_api_key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self._settings.zhihuiya_base_url, timeout=self._settings.http_timeout, trust_env=False, headers=self._headers()) as client:
                response = await client.request(method, path, json=json_body, params=params)
                body = response.json()
        except Exception as exc:
            return {"status": False, "error_code": -1, "error_msg": f"network_or_parse_error: {exc}", "data": None}
        if not isinstance(body, dict):
            return {"status": False, "error_code": -1, "error_msg": "response_not_json_object", "data": None}
        return body

    async def search(self, query_text: str, limit: int, offset: int) -> dict[str, Any]:
        return await self._request("POST", "/search/patent/query-search-patent/v2", json_body={"query_text": query_text, "limit": limit, "offset": offset})

    async def bibliography(self, patent_number: str) -> dict[str, Any]:
        return await self._request("GET", "/basic-patent-data/bibliography", params={"patent_number": patent_number})

    async def patent_info(self, patent_numbers: list[str]) -> dict[str, Any]:
        return await self._request("POST", "/shhgy/reportdata/patent-info", json_body={"patent_number": patent_numbers})
