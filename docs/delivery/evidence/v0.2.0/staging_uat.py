#!/usr/bin/env python3
"""Staging UAT for v0.2.0 — docs/delivery/050-v0.2.0-uat.md."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

BASE = "http://127.0.0.1:8001"
JOURNEY = Path(__file__).resolve().parents[4] / "examples" / "journeys" / "order-to-cash.yaml"
OUT = Path(__file__).resolve().parent / "staging-uat.log"


async def main() -> int:
    results: list[dict] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        # P2 submit
        raw = yaml.safe_load(JOURNEY.read_text(encoding="utf-8"))
        imp = await client.post("/api/v1/journeys/import", json=raw)
        results.append({"id": "v020-P2-import", "status": imp.status_code, "pass": imp.status_code in (200, 201, 409)})

        sub = await client.post(
            "/api/v1/executions/",
            json={"journey_id": raw["metadata"]["id"], "mode": "full"},
        )
        ok_sub = sub.status_code == 202
        eid = sub.json().get("execution_id") if ok_sub else None
        results.append({"id": "v020-P2-submit", "pass": ok_sub, "execution_id": eid})

        # P3 progress
        terminal = None
        if eid:
            for _ in range(60):
                detail = await client.get(f"/api/v1/executions/{eid}")
                body = detail.json()
                terminal = body.get("status")
                if terminal in {"succeeded", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.2)
        results.append({"id": "v020-P3-progress", "pass": terminal == "succeeded", "status": terminal})

        # P4 SSE — subscribe while execution is running
        sse_ok = False
        if eid:
            sub_sse = await client.post(
                "/api/v1/executions/",
                json={"journey_id": raw["metadata"]["id"], "mode": "full"},
            )
            sse_eid = sub_sse.json().get("execution_id")
            if sse_eid:
                start = time.time()
                async with client.stream("GET", f"/api/v1/executions/{sse_eid}/stream") as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data:") and "execution" in line:
                            sse_ok = time.time() - start < 5
                            break
                        if time.time() - start > 10:
                            break
        results.append({"id": "v020-P4-sse", "pass": sse_ok})

        # P5 pause/resume/cancel on fresh execution
        sub2 = await client.post(
            "/api/v1/executions/",
            json={"journey_id": raw["metadata"]["id"], "mode": "full"},
        )
        eid2 = sub2.json().get("execution_id")
        await client.post(f"/api/v1/executions/{eid2}/cancel")
        cancel = await client.get(f"/api/v1/executions/{eid2}")
        results.append(
            {
                "id": "v020-P5-cancel",
                "pass": cancel.json().get("status") == "cancelled",
            }
        )

    passed = sum(1 for r in results if r.get("pass"))
    summary = {"passed": passed, "total": len(results), "results": results}
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
