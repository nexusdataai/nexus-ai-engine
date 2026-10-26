"""HTTP helpers for live ai-engine queue / journey APIs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class TimedResponse:
    status_code: int
    elapsed_s: float
    json: dict[str, Any] | list[Any] | None
    text: str
    error: str | None = None


class LiveAiEngineClient:
    def __init__(self, base_url: str, *, timeout_s: float = 120.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> TimedResponse:
        url = f"{self._base}{path}"
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s or self._timeout) as client:
                resp = await client.request(method, url, json=json_body)
            elapsed = time.perf_counter() - started
            body_text = resp.text
            parsed: dict[str, Any] | list[Any] | None
            try:
                parsed = resp.json()
            except Exception:
                parsed = None
            return TimedResponse(
                status_code=resp.status_code,
                elapsed_s=elapsed,
                json=parsed if isinstance(parsed, (dict, list)) else None,
                text=body_text[:2000],
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            return TimedResponse(
                status_code=0,
                elapsed_s=elapsed,
                json=None,
                text="",
                error=str(exc),
            )

    async def queue_summary(self) -> TimedResponse:
        return await self._request("GET", "/api/v1/queue/summary", timeout_s=60.0)

    async def queue_jobs(self, *, limit: int = 200) -> TimedResponse:
        return await self._request(
            "GET",
            f"/api/v1/queue/jobs?state=all&limit={limit}",
            timeout_s=90.0,
        )

    async def queue_purge(self) -> TimedResponse:
        return await self._request("POST", "/api/v1/queue/purge", timeout_s=60.0)

    async def list_journey_ids(self, *, limit: int = 1000) -> tuple[list[str], TimedResponse]:
        resp = await self._request("GET", f"/api/v1/journeys/?limit={limit}", timeout_s=120.0)
        ids: list[str] = []
        if resp.status_code == 200 and isinstance(resp.json, dict):
            for row in resp.json.get("data") or []:
                if isinstance(row, dict):
                    jid = row.get("journeyId") or row.get("journey_id")
                    if jid:
                        ids.append(str(jid))
        return ids, resp

    async def bulk_run(self, journey_ids: list[str], *, triggered_by: str = "endurance") -> TimedResponse:
        return await self._request(
            "POST",
            "/api/v1/journeys/bulk-run",
            json_body={"journey_ids": journey_ids, "triggered_by": triggered_by},
            timeout_s=300.0,
        )

    async def health(self) -> TimedResponse:
        return await self._request("GET", "/health", timeout_s=15.0)
