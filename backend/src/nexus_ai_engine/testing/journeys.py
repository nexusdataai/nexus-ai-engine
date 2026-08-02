"""End-to-end plugin-journey YAML runner.

Two modes:

- **Parse-only** (no app bound): validates shape of the YAML and returns
  ``status='validated'``.
- **Live** (app bound): creates a journey via the in-process API, runs the
  job, polls to a terminal state, and returns ``status=completed|failed|
  cancelled`` along with logs + metrics. Used by
  ``nexus-ai-engine run-journey path/to.yaml``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class JourneyRunResult:
    ok: bool
    status: str
    journey_id: Optional[str] = None
    job_id: Optional[str] = None
    stage_id: Optional[str] = None
    logs: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"Journey run: status={self.status} ok={self.ok}"]
        if self.journey_id:
            parts.append(f"  journey_id = {self.journey_id}")
        if self.stage_id:
            parts.append(f"  stage_id   = {self.stage_id}")
        if self.job_id:
            parts.append(f"  job_id     = {self.job_id}")
        if self.errors:
            parts.append("  errors:")
            parts.extend(f"    - {err}" for err in self.errors)
        if self.metrics:
            parts.append("  metrics:")
            parts.extend(f"    {k} = {v}" for k, v in self.metrics.items())
        if self.logs:
            parts.append(f"  logs: {len(self.logs)} line(s)")
        return "\n".join(parts)


class JourneyYAMLRunner:
    """Run a plugin-journey YAML either offline (parse-only) or against an
    in-process FastAPI app for full execution."""

    def __init__(self, app: Optional[Any] = None, *, poll_timeout_seconds: float = 30.0) -> None:
        self._app = app
        self._timeout = poll_timeout_seconds

    def run(self, yaml_path: str | Path) -> JourneyRunResult:
        path = Path(yaml_path)
        if not path.exists():
            return JourneyRunResult(ok=False, status="missing", errors=[f"File not found: {path}"])

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            return JourneyRunResult(ok=False, status="invalid_yaml", errors=[str(exc)])

        if not isinstance(payload, dict):
            return JourneyRunResult(
                ok=False,
                status="invalid_shape",
                errors=["Top-level YAML document must be a mapping."],
            )

        name = payload.get("name") or payload.get("journey_name")
        stage = payload.get("stage") or payload.get("journey_stage") or {}
        steps = stage.get("steps") if isinstance(stage, dict) else None

        missing: list[str] = []
        if not name:
            missing.append("name")
        if not isinstance(stage, dict):
            missing.append("stage")
        if not isinstance(steps, list) or not steps:
            missing.append("stage.steps (non-empty list)")

        if missing:
            return JourneyRunResult(
                ok=False,
                status="invalid_shape",
                errors=[f"Missing or malformed fields: {', '.join(missing)}"],
            )

        if self._app is None:
            return JourneyRunResult(
                ok=True,
                status="validated",
                journey_id=str(name),
                stage_id=stage.get("id") if isinstance(stage, dict) else None,
                metrics={"steps": len(steps)},
            )

        return self._run_live(name, stage, steps)

    # ── Live mode ────────────────────────────────────────────────────────

    def _run_live(self, name: str, stage: dict, steps: list) -> JourneyRunResult:
        try:
            import asyncio

            import httpx
        except ImportError:  # pragma: no cover
            return JourneyRunResult(
                ok=False,
                status="missing_dep",
                errors=["httpx is required for live runs; install nexus-ai-engine[harness]"],
            )

        stage_id = stage.get("id") or "stage-1"
        stage_payload = {
            "id": stage_id,
            "name": stage.get("name") or stage_id,
            "description": stage.get("description"),
            "order": 1,
            "status": "pending",
            "steps": [
                {
                    "id": s.get("id") or f"step-{i+1}",
                    "name": s.get("name") or f"Step {i+1}",
                    "description": s.get("description"),
                    "order": i + 1,
                    # Preserve plugin-journey fields so the engine's
                    # deterministic step-tool dispatch can see them.
                    "type": s.get("type"),
                    "tool": s.get("tool"),
                    "input": s.get("input"),
                }
                for i, s in enumerate(steps)
            ],
        }

        async def _drive() -> JourneyRunResult:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver", timeout=self._timeout
            ) as c:
                created = await c.post(
                    "/api/v1/journeys/",
                    json={
                        "name": name,
                        "description": "Created by JourneyYAMLRunner",
                        "capability": "yaml-runner",
                        "stages": [stage_payload],
                    },
                )
                if created.status_code >= 400:
                    return JourneyRunResult(
                        ok=False, status="create_failed", errors=[created.text]
                    )
                journey_id = created.json()["id"]

                run = await c.post(
                    f"/api/v1/journeys/{journey_id}/jobs",
                    json={"stage_id": stage_id, "reason": "retry yaml-runner"},
                )
                if run.status_code >= 400:
                    return JourneyRunResult(
                        ok=False, status="run_failed", journey_id=journey_id,
                        stage_id=stage_id, errors=[run.text],
                    )
                job_id = run.json()["id"]

                deadline = time.time() + self._timeout
                final_status = "running"
                while time.time() < deadline:
                    status_body = (
                        await c.get(f"/api/v1/journeys/{journey_id}/jobs/{job_id}/status")
                    ).json()
                    final_status = status_body["status"]
                    if final_status != "running":
                        break
                    await asyncio.sleep(0.2)

                logs = (
                    await c.get(f"/api/v1/journeys/{journey_id}/jobs/{job_id}/logs")
                ).json()
                final_job = (
                    await c.get(f"/api/v1/journeys/{journey_id}/jobs/{job_id}")
                ).json()

                return JourneyRunResult(
                    ok=final_status == "completed",
                    status=final_status,
                    journey_id=journey_id,
                    job_id=job_id,
                    stage_id=stage_id,
                    logs=logs,
                    metrics={
                        "steps": len(steps),
                        "duration_seconds": final_job.get("duration_seconds"),
                        **(final_job.get("metrics") or {}),
                    },
                )

        try:
            # If we are already inside a running loop (e.g. pytest-asyncio),
            # we cannot call asyncio.run; fall back to a private loop.
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is None:
                return asyncio.run(_drive())
            # Inside a running loop — spin a private thread to execute.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_drive())).result()
        except Exception as exc:
            return JourneyRunResult(ok=False, status="error", errors=[str(exc)])
