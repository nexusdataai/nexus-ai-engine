"""Connector HTTP client — POST /api/v1/connectors/{id}/invoke."""

from __future__ import annotations

from typing import Any

import httpx

from nexus_tool_sdk.context import ExecutionContext
from nexus_tool_sdk.errors import ConnectorError

_RETRYABLE_STATUS = frozenset({429, 503})


def _connector_error_from_response(resp: httpx.Response) -> ConnectorError:
    body: dict[str, Any] = {}
    try:
        body = resp.json()
    except Exception:
        pass
    err = body.get("error") if isinstance(body.get("error"), dict) else body
    if not isinstance(err, dict):
        err = body
    code = str(err.get("code") or f"http_{resp.status_code}")
    message = str(err.get("message") or body.get("detail") or resp.reason_phrase or "Connector request failed")
    retryable = resp.status_code in _RETRYABLE_STATUS or bool(err.get("retryable"))
    return ConnectorError(code, message, retryable=retryable, status_code=resp.status_code, details=body)


class ConnectorClient:
    """Client for ontology unified connector invoke API."""

    def __init__(
        self,
        base_url: str,
        http: httpx.AsyncClient,
        context: ExecutionContext,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http
        self._context = context

    def _headers(self) -> dict[str, str]:
        return self._context.forward_headers()

    async def invoke(self, connector_id: str, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": action,
            "arguments": arguments,
            "context": self._context.to_dict(),
        }
        if self._context.idempotency_key is not None:
            payload["idempotencyKey"] = self._context.idempotency_key

        resp = await self._http.post(
            f"{self._base_url}/{connector_id}/invoke",
            json=payload,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            raise _connector_error_from_response(resp)

        body = resp.json()
        if not body.get("success", True):
            err = body.get("error") or {}
            raise ConnectorError(
                str(err.get("code", "connector_error")),
                str(err.get("message", "connector invoke failed")),
                retryable=bool(err.get("retryable")),
                details=err if isinstance(err, dict) else {"error": err},
            )
        result = body.get("result")
        if not isinstance(result, dict):
            return {"value": result}
        return result
