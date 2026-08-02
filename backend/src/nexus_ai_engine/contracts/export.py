"""Export contract JSON Schemas to disk.

Usage::

    python -m nexus_ai_engine.contracts.export --out schemas/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from nexus_ai_engine.contracts.execution_graph import ExecutionGraph
from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition
from nexus_ai_engine.contracts.tool_request import ToolRequest, ToolResponse

ROOT_MODELS: dict[str, type[BaseModel]] = {
    "journey-dsl-v1": JourneyDefinition,
    "execution-graph": ExecutionGraph,
    "tool-request": ToolRequest,
    "tool-response": ToolResponse,
}


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for slug, model in ROOT_MODELS.items():
        schema = model.model_json_schema()
        target = out_dir / f"{slug}.schema.json"
        target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(prog="nexus-ai-engine-contracts-export")
    parser.add_argument("--out", default="schemas", type=Path)
    args = parser.parse_args()
    written = export_all(args.out)
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
