from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientConnectorError, ClientResponse, ClientSession, FormData

from .types import MetaAccount


@dataclass(slots=True)
class MetaGraphError(Exception):
    message: str
    status: int | None = None
    code: int | None = None
    error_subcode: int | None = None
    fbtrace_id: str | None = None
    payload: dict[str, Any] | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.status:
            parts.append(f"status={self.status}")
        if self.code:
            parts.append(f"code={self.code}")
        if self.error_subcode:
            parts.append(f"subcode={self.error_subcode}")
        if self.fbtrace_id:
            parts.append(f"fbtrace_id={self.fbtrace_id}")
        return f"{parts[0]} (" + ", ".join(parts[1:]) + ")" if len(parts) > 1 else parts[0]


class MetaGraphClient:
    log = logging.getLogger("meta.graph")

    def __init__(self, session: ClientSession) -> None:
        self.http = session

    @staticmethod
    def _url(account: MetaAccount, path: str) -> str:
        path = path.lstrip("/")
        return f"{account.graph_base_url}/{account.graph_version}/{path}"

    @staticmethod
    def _headers(account: MetaAccount, headers: dict[str, str] | None = None) -> dict[str, str]:
        result = {"Authorization": f"Bearer {account.access_token}"}
        if headers:
            result.update(headers)
        return result

    async def request(
        self,
        account: MetaAccount,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self._url(account, path)
        safe_headers = self._headers(account, headers)
        self.log.debug("Meta Graph %s %s", method, url)
        try:
            response = await self.http.request(
                method,
                url,
                json=json,
                data=data,
                params=params,
                headers=safe_headers,
            )
        except ClientConnectorError as err:
            raise MetaGraphError(f"Could not connect to Meta Graph: {err}") from err
        return await self._decode_response(response)

    async def _decode_response(self, response: ClientResponse) -> dict[str, Any]:
        try:
            payload = await response.json(content_type=None)
        except Exception:
            text = await response.text()
            payload = {"raw": text}

        if response.status >= 400 or payload.get("error"):
            error = payload.get("error") or {}
            raise MetaGraphError(
                message=error.get("message") or payload.get("raw") or "Meta Graph API error",
                status=response.status,
                code=error.get("code"),
                error_subcode=error.get("error_subcode"),
                fbtrace_id=error.get("fbtrace_id"),
                payload=payload,
            )
        return payload

    async def send_message(self, account: MetaAccount, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request(
            account,
            "POST",
            f"/{account.send_asset_id}/messages",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    async def mark_whatsapp_read(self, account: MetaAccount, message_id: str) -> dict[str, Any]:
        return await self.send_message(
            account,
            {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
        )

    async def upload_whatsapp_media(
        self,
        account: MetaAccount,
        data_file: bytes,
        *,
        file_name: str,
        file_type: str,
    ) -> dict[str, Any]:
        form_data = FormData()
        form_data.add_field("file", data_file, filename=file_name, content_type=file_type)
        form_data.add_field("messaging_product", "whatsapp")
        form_data.add_field("type", file_type)
        return await self.request(
            account, "POST", f"/{account.send_asset_id}/media", data=form_data
        )

    async def get_media_metadata(self, account: MetaAccount, media_id: str) -> dict[str, Any]:
        return await self.request(account, "GET", f"/{media_id}")

    async def download_url(self, account: MetaAccount, url: str) -> ClientResponse:
        self.log.debug("Downloading Meta media URL")
        try:
            response = await self.http.get(url, headers=self._headers(account))
        except ClientConnectorError as err:
            raise MetaGraphError(f"Could not download Meta media: {err}") from err
        if response.status >= 400:
            raise MetaGraphError("Could not download Meta media", status=response.status)
        return response

    async def download_media(self, account: MetaAccount, media_id: str) -> ClientResponse:
        metadata = await self.get_media_metadata(account, media_id)
        media_url = metadata.get("url")
        if not media_url:
            raise MetaGraphError("Meta media metadata response did not include a URL")
        return await self.download_url(account, media_url)
