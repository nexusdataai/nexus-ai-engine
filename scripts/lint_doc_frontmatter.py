#!/usr/bin/env python3
"""Validate YAML front-matter on planning and delivery docs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REQUIRED_DELIVERY = ("id", "title", "module", "status", "version", "owners", "depends_on", "adrs")
REQUIRED_SPRINT = ("sprint", "title", "release", "status")

SKIP_RELATIVE = {
    Path("docs/prompts"),
    Path("docs/spec"),
    Path("docs/user-guide"),
    Path("docs/dev-plan/build"),
}


def _parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return None
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return None
    block = "\n".join(lines[1:end])
    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        return None
    return data


def _missing_fields(data: dict, required: tuple[str, ...]) -> list[str]:
    return [field for field in required if field not in data]


def lint_file(path: Path, repo_root: Path) -> list[str]:
    rel = path.relative_to(repo_root)
    for skip in SKIP_RELATIVE:
        if skip in rel.parents or rel.parent == skip:
            return []

    if path.name == "README.md":
        return []

    text = path.read_text(encoding="utf-8")
    data = _parse_frontmatter(text)
    if data is None:
        return [f"{rel}: missing or invalid YAML front-matter (must start with ---)"]

    if rel.parts[-2] == "sprints":
        missing = _missing_fields(data, REQUIRED_SPRINT)
    else:
        missing = _missing_fields(data, REQUIRED_DELIVERY)

    if missing:
        return [f"{rel}: missing front-matter fields: {', '.join(missing)}"]
    return []


def collect_targets(docs_root: Path) -> list[Path]:
    return sorted(docs_root.rglob("*.md"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Documentation root relative to repo (default: docs)",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    docs_root = repo_root / args.docs_root
    if not docs_root.is_dir():
        print(f"ERROR: docs root not found: {docs_root}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in collect_targets(docs_root):
        errors.extend(lint_file(path, repo_root))

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"OK: doc front-matter lint passed ({len(collect_targets(docs_root))} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
