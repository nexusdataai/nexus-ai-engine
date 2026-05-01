"""Endurance smoke — concurrent hits against the in-process health endpoint.

The heavy scenarios (thousands of concurrent journey runs) are tagged
``@pytest.mark.heavy`` and skipped by ``make test-endurance``; run them
with ``make test-endurance-full`` or the nightly CI job.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_under_light_concurrency(http_client, gather_n) -> None:
    async def hit() -> int:
        resp = await http_client.get("/health")
        return resp.status_code

    results = await gather_n(20, hit)
    assert all(code == 200 for code in results), results


@pytest.mark.heavy
@pytest.mark.asyncio
async def test_health_under_heavy_concurrency(http_client, gather_n) -> None:
    async def hit() -> int:
        resp = await http_client.get("/health")
        return resp.status_code

    results = await gather_n(500, hit)
    assert all(code == 200 for code in results), results
