#!/usr/bin/env python3
"""
Adapter: pytest-json-report output -> EnduranceReportGenerator schema.

nexus-ai-engine's endurance tier runs as pytest (`pytest tests/endurance`),
but `endurance_report_generator.py` (lifted verbatim from nexus-backend)
expects the JSON shape produced by nexus-backend's custom endurance harness
(test_info / summary / performance / health / failures / config).

This adapter reads a pytest-json-report file and writes the endurance
schema the generator understands. CPU / memory / alerts are left empty
because the pytest-based endurance tier does not collect them.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _outcome_counts(tests: list[dict]) -> tuple[int, int, int, int]:
    passed = sum(1 for t in tests if t.get("outcome") == "passed")
    failed = sum(1 for t in tests if t.get("outcome") == "failed")
    errors = sum(1 for t in tests if t.get("outcome") == "error")
    skipped = sum(1 for t in tests if t.get("outcome") == "skipped")
    return passed, failed, errors, skipped


def _durations(tests: list[dict]) -> tuple[float, float, float]:
    durs = [float(t.get("duration", 0) or 0) for t in tests]
    if not durs:
        return 0.0, 0.0, 0.0
    return min(durs), sum(durs) / len(durs), max(durs)


def convert(pytest_json_path: Path, output_path: Path) -> None:
    with pytest_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    tests = data.get("tests", []) or []
    summary = data.get("summary", {}) or {}

    passed, failed, errors, _skipped = _outcome_counts(tests)
    total = summary.get("total", len(tests)) or len(tests)
    duration_seconds = float(data.get("duration", 0) or 0)
    pass_rate = (passed / total * 100) if total else 0.0
    tests_per_minute = (total / (duration_seconds / 60)) if duration_seconds > 0 else 0.0

    min_d, avg_d, max_d = _durations(tests)
    created_ts = data.get("created", 0)
    try:
        start_iso = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat() if created_ts else ""
    except (OSError, ValueError):
        start_iso = ""

    endurance = {
        "test_info": {
            "duration_seconds": duration_seconds,
            "start_time": start_iso,
            "end_time": datetime.now(tz=timezone.utc).isoformat(),
            "interrupted": False,
            "strategy": "pytest",
        },
        "summary": {
            "total_tests": total,
            "total_iterations": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": pass_rate,
            "tests_per_minute": tests_per_minute,
        },
        "performance": {
            "avg_execution_time": avg_d,
            "max_execution_time": max_d,
            "min_execution_time": min_d,
        },
        "health": {
            "healthy": failed == 0 and errors == 0,
            "alerts": [],
            "summary": {
                "cpu": {},
                "memory_gb": {},
                "duration_seconds": int(duration_seconds),
                "samples_collected": 0,
                "threads": {},
                "file_descriptors": {},
            },
        },
        "failures": {
            t.get("nodeid", "?"): (t.get("call", {}) or {}).get("longrepr", "")
            for t in tests
            if t.get("outcome") in ("failed", "error")
        },
        "config": {},
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(endurance, f, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", required=True, help="pytest-json-report JSON file")
    parser.add_argument("--output", "-o", required=True, help="Endurance-schema JSON output")
    args = parser.parse_args()

    convert(Path(args.input), Path(args.output))
    print(f"converted {args.input} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
