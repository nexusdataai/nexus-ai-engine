"""Repeated bulk-run of all journeys with queue health checks."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import LiveAiEngineClient, TimedResponse


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class SoakIssue:
    kind: str
    message: str
    cycle: int | None = None


@dataclass
class SoakCycleStats:
    cycle: int
    bulk_elapsed_s: float
    queued: int
    failed: int
    drain_elapsed_s: float | None
    drained: bool
    peak_lag: int = 0
    peak_active: int = 0
    peak_queued: int = 0


@dataclass
class SoakReport:
    base_url: str
    journey_count: int
    duration_limit_s: float
    started_at: float
    ended_at: float
    cycles_completed: int
    issues: list[SoakIssue] = field(default_factory=list)
    cycles: list[SoakCycleStats] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def summary_text(self) -> str:
        lines = [
            f"base_url={self.base_url}",
            f"journeys={self.journey_count}",
            f"cycles={self.cycles_completed}",
            f"elapsed_s={self.ended_at - self.started_at:.1f}",
            f"issues={len(self.issues)}",
        ]
        for issue in self.issues[:20]:
            lines.append(f"  [{issue.kind}] cycle={issue.cycle} {issue.message}")
        if len(self.issues) > 20:
            lines.append(f"  ... and {len(self.issues) - 20} more")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "journey_count": self.journey_count,
            "duration_limit_s": self.duration_limit_s,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "cycles_completed": self.cycles_completed,
            "ok": self.ok,
            "issues": [{"kind": i.kind, "message": i.message, "cycle": i.cycle} for i in self.issues],
            "cycles": [c.__dict__ for c in self.cycles],
        }


class BulkRunSoakRunner:
    def __init__(
        self,
        base_url: str,
        *,
        duration_s: float | None = None,
        drain_timeout_s: float | None = None,
        summary_max_s: float | None = None,
        jobs_max_s: float | None = None,
        poll_interval_s: float | None = None,
        min_journeys: int | None = None,
        purge_between_cycles: bool | None = None,
        report_path: Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.duration_s = duration_s if duration_s is not None else _env_float("ENDURANCE_DURATION_SECONDS", 1800.0)
        self.drain_timeout_s = drain_timeout_s if drain_timeout_s is not None else _env_float(
            "ENDURANCE_DRAIN_TIMEOUT_SECONDS", 1200.0
        )
        self.summary_max_s = summary_max_s if summary_max_s is not None else _env_float(
            "ENDURANCE_SUMMARY_MAX_SECONDS", 5.0
        )
        self.jobs_max_s = jobs_max_s if jobs_max_s is not None else _env_float("ENDURANCE_JOBS_MAX_SECONDS", 15.0)
        self.poll_interval_s = poll_interval_s if poll_interval_s is not None else _env_float(
            "ENDURANCE_POLL_INTERVAL_SECONDS", 10.0
        )
        self.min_journeys = min_journeys if min_journeys is not None else _env_int("ENDURANCE_MIN_JOURNEYS", 55)
        self.purge_between_cycles = (
            purge_between_cycles
            if purge_between_cycles is not None
            else _env_bool("ENDURANCE_QUEUE_PURGE_BETWEEN_CYCLES", False)
        )
        self.report_path = report_path or Path(
            os.getenv("ENDURANCE_REPORT_PATH", "tests/reports/endurance/bulk_run_55_soak.json")
        )
        self._client = LiveAiEngineClient(self.base_url)

    def _record_http_issue(self, issues: list[SoakIssue], cycle: int, label: str, resp: TimedResponse) -> None:
        if resp.error:
            issues.append(SoakIssue("http_error", f"{label}: {resp.error}", cycle=cycle))
            return
        if resp.status_code == 0:
            issues.append(SoakIssue("http_error", f"{label}: no response", cycle=cycle))
            return
        if resp.status_code >= 500 or resp.status_code in (502, 503):
            issues.append(
                SoakIssue(
                    "queue_unavailable",
                    f"{label}: HTTP {resp.status_code} in {resp.elapsed_s:.2f}s",
                    cycle=cycle,
                )
            )
        elif resp.status_code >= 400:
            issues.append(
                SoakIssue("http_error", f"{label}: HTTP {resp.status_code} body={resp.text[:200]}", cycle=cycle)
            )

    def _record_slow(self, issues: list[SoakIssue], cycle: int, label: str, resp: TimedResponse, max_s: float) -> None:
        if resp.error or resp.status_code >= 400:
            return
        if resp.elapsed_s > max_s:
            issues.append(
                SoakIssue("slow_api", f"{label}: {resp.elapsed_s:.2f}s > {max_s}s", cycle=cycle)
            )

    async def _wait_for_drain(
        self,
        issues: list[SoakIssue],
        cycle: int,
        stats: SoakCycleStats,
        *,
        drain_start: float,
        absolute_deadline: float,
    ) -> None:
        per_cycle_deadline = drain_start + self.drain_timeout_s
        deadline = min(per_cycle_deadline, absolute_deadline)
        while time.monotonic() < deadline:
            summary = await self._client.queue_summary()
            self._record_http_issue(issues, cycle, "queue/summary", summary)
            self._record_slow(issues, cycle, "queue/summary", summary, self.summary_max_s)

            jobs = await self._client.queue_jobs()
            self._record_http_issue(issues, cycle, "queue/jobs", jobs)
            self._record_slow(issues, cycle, "queue/jobs", jobs, self.jobs_max_s)

            if summary.status_code == 200 and isinstance(summary.json, dict):
                snap = summary.json
                stats.peak_lag = max(stats.peak_lag, int(snap.get("lag") or 0))
                stats.peak_active = max(stats.peak_active, int(snap.get("active") or 0))
                stats.peak_queued = max(stats.peak_queued, int(snap.get("queued") or 0))
                lag = int(snap.get("lag") or 0)
                active = int(snap.get("active") or 0)
                queued = int(snap.get("queued") or 0)
                if lag == 0 and active == 0 and queued == 0:
                    stats.drained = True
                    stats.drain_elapsed_s = time.monotonic() - drain_start
                    return

            await asyncio.sleep(self.poll_interval_s)

        stats.drained = False
        waited = time.monotonic() - drain_start
        issues.append(
            SoakIssue(
                "drain_timeout",
                f"queue not idle after {waited:.0f}s "
                f"(peak lag={stats.peak_lag} active={stats.peak_active} queued={stats.peak_queued})",
                cycle=cycle,
            )
        )

    async def run(self) -> SoakReport:
        issues: list[SoakIssue] = []
        cycles: list[SoakCycleStats] = []
        started = time.monotonic()
        deadline = started + self.duration_s
        cycle = 0

        health = await self._client.health()
        self._record_http_issue(issues, None, "health", health)

        journey_ids, list_resp = await self._client.list_journey_ids()
        self._record_http_issue(issues, None, "journeys/list", list_resp)
        if len(journey_ids) < self.min_journeys:
            issues.append(
                SoakIssue(
                    "setup",
                    f"expected >={self.min_journeys} journeys, got {len(journey_ids)}",
                    cycle=None,
                )
            )
            ended = time.monotonic()
            report = SoakReport(
                base_url=self.base_url,
                journey_count=len(journey_ids),
                duration_limit_s=self.duration_s,
                started_at=started,
                ended_at=ended,
                cycles_completed=0,
                issues=issues,
                cycles=cycles,
            )
            self._write_report(report)
            return report

        min_cycle_budget_s = 120.0
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining < min_cycle_budget_s:
                break

            cycle += 1
            stats = SoakCycleStats(cycle=cycle, bulk_elapsed_s=0.0, queued=0, failed=0, drain_elapsed_s=None, drained=False)

            if self.purge_between_cycles and cycle > 1:
                purge = await self._client.queue_purge()
                self._record_http_issue(issues, cycle, "queue/purge", purge)

            bulk = await self._client.bulk_run(journey_ids)
            stats.bulk_elapsed_s = bulk.elapsed_s
            self._record_http_issue(issues, cycle, "journeys/bulk-run", bulk)

            if bulk.status_code == 200 and isinstance(bulk.json, dict):
                stats.queued = int(bulk.json.get("queued") or 0)
                stats.failed = int(bulk.json.get("failed") or 0)
                if stats.failed > 0:
                    issues.append(
                        SoakIssue("bulk_run", f"failed={stats.failed} message={bulk.json.get('message')}", cycle=cycle)
                    )
                if stats.queued != len(journey_ids):
                    issues.append(
                        SoakIssue(
                            "bulk_run",
                            f"queued={stats.queued} expected={len(journey_ids)}",
                            cycle=cycle,
                        )
                    )
            elif bulk.status_code == 200:
                issues.append(SoakIssue("bulk_run", "unexpected non-JSON bulk-run response", cycle=cycle))

            drain_start = time.monotonic()
            await self._wait_for_drain(
                issues,
                cycle,
                stats,
                drain_start=drain_start,
                absolute_deadline=deadline,
            )

            cycles.append(stats)

        ended = time.monotonic()
        report = SoakReport(
            base_url=self.base_url,
            journey_count=len(journey_ids),
            duration_limit_s=self.duration_s,
            started_at=started,
            ended_at=ended,
            cycles_completed=len(cycles),
            issues=issues,
            cycles=cycles,
        )
        self._write_report(report)
        return report

    def _write_report(self, report: SoakReport) -> None:
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        except OSError:
            pass


async def _main() -> int:
    base = os.getenv("ENDURANCE_BASE_URL", "").strip()
    if not base:
        print("Set ENDURANCE_BASE_URL (e.g. https://ai-engine.yourbrain.tech)")
        return 2
    runner = BulkRunSoakRunner(base)
    report = await runner.run()
    print(report.summary_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
