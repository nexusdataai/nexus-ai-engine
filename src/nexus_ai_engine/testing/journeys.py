"""End-to-end plugin-journey YAML runner.

Loads a plugin-journey YAML, creates a journey via the in-process API, adds
its stage, runs the job, streams SSE, and returns a structured result. Full
functionality activates in phase 9 when journey/job routes go live. Until
then the runner performs the load + parse pass so YAMLs can be validated
today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class JourneyRunResult:
    """Outcome of running a plugin-journey YAML end-to-end."""

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
        header = f"Journey run: status={self.status} ok={self.ok}"
        parts = [header]
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
        return "\n".join(parts)


class JourneyYAMLRunner:
    """Run a plugin-journey YAML against an in-process harness.

    Phase-1 behavior: validate that the YAML parses, carries a recognizable
    shape (``name``, ``stage`` with ``steps``), and return a JourneyRunResult
    with ``status='validated'``. Phase-9 behavior (full run) lands when
    journey/job routes are activated.
    """

    def __init__(self, app: Optional[Any] = None) -> None:
        self._app = app

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

        return JourneyRunResult(
            ok=False,
            status="pending_phase_9",
            errors=[
                "Full end-to-end runner activates in phase 9 when journey/job routes go live. "
                "YAML validated successfully."
            ],
            metrics={"steps": len(steps)},
        )
