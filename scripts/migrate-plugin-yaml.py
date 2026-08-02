#!/usr/bin/env python3
"""Migrate legacy plugin-journey YAML to Journey DSL v1 format."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def migrate_document(payload: dict) -> dict:
    """Convert plugin-style journey YAML to nexus.ai/v1 Journey DSL."""
    name = payload.get("name") or payload.get("journey_name")
    if not name:
        raise ValueError("missing name")

    stage = payload.get("stage") or payload.get("journey_stage") or {}
    steps = stage.get("steps") if isinstance(stage, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError("missing stage.steps")

    dsl_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        sid = step.get("id", "").replace("-", "_")
        if sid and sid[0].isdigit():
            sid = f"s_{sid}"
        dsl_step: dict = {"id": sid or "step"}
        if step.get("name"):
            dsl_step["name"] = step["name"]
        if step.get("tool"):
            dsl_step["tool"] = step["tool"]
        if step.get("type") and step["type"] != "tool":
            dsl_step["type"] = step["type"]
        params = step.get("params") or step.get("input") or {}
        if params:
            dsl_step["params"] = params
        if step.get("foreach"):
            dsl_step["foreach"] = step["foreach"]
        if step.get("logic"):
            dsl_step["logic"] = step["logic"]
        dsl_steps.append(dsl_step)

    journey_id = str(name).lower().replace("_", "-")
    stage_id = (stage.get("id") or "main").replace("-", "_")

    return {
        "apiVersion": "nexus.ai/v1",
        "kind": "Journey",
        "metadata": {"id": journey_id, "version": 1},
        "spec": {
            "display_name": payload.get("display_name") or name.replace("-", " ").title(),
            "description": payload.get("description") or stage.get("description") or "",
            "trigger": payload.get("trigger") or "manual",
            "stages": [
                {
                    "id": stage_id,
                    "name": stage.get("name") or stage_id,
                    "description": stage.get("description") or "",
                    "steps": dsl_steps,
                }
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate plugin journey YAML to Journey DSL v1")
    parser.add_argument("--input", type=Path, required=True, help="Input YAML file or directory")
    parser.add_argument("--output", type=Path, help="Output directory (required unless --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Validate migration without writing")
    args = parser.parse_args(argv)

    inputs: list[Path] = []
    if args.input.is_file():
        inputs = [args.input]
    elif args.input.is_dir():
        inputs = sorted(args.input.glob("*.yaml"))
    else:
        print(f"input not found: {args.input}", file=sys.stderr)
        return 1

    if not args.dry_run and not args.output:
        print("--output is required unless --dry-run", file=sys.stderr)
        return 1

    if args.output and not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)

    ok = 0
    for path in inputs:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("top-level must be a mapping")
            if payload.get("apiVersion") == "nexus.ai/v1":
                print(f"skip (already DSL): {path.name}")
                ok += 1
                continue
            migrated = migrate_document(payload)
            from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition

            JourneyDefinition.model_validate(migrated)
            out_name = path.stem.replace("_", "-") + "-dsl.yaml"
            if args.dry_run:
                print(f"ok (dry-run): {path.name} -> {out_name} ({len(migrated['spec']['stages'][0]['steps'])} steps)")
            else:
                out_path = args.output / out_name
                out_path.write_text(yaml.safe_dump(migrated, sort_keys=False), encoding="utf-8")
                print(f"wrote: {out_path}")
            ok += 1
        except Exception as exc:
            print(f"fail: {path.name}: {exc}", file=sys.stderr)

    print(f"migrated {ok}/{len(inputs)} file(s)")
    return 0 if ok == len(inputs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
