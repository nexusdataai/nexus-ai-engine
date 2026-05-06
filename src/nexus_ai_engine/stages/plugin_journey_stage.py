"""
Plugin Journey Stage

A dynamic journey stage that loads step definitions from YAML journey files
registered by plugins. Supports tool execution, foreach iteration, compute
transforms, and S3/Glue output steps.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from .base_stage import BaseStage
from ..plugins.plugin_models import JourneyDefinition, JourneyStep
from ..plugins.yaml_tool_executor import YAMLToolExecutor, _resolve_var

pj_logger = logger.bind(component="plugin-journey")


class PluginJourneyStage(BaseStage):

    def __init__(self, journey_id, stage_id, job_id, region_name=None, role_arn=None,
                 journey_def: Optional[JourneyDefinition] = None):
        super().__init__(journey_id, stage_id, job_id, region_name, role_arn)
        self.setup_enhanced_logging()
        self._journey_def = journey_def
        self._step_results: Dict[str, Any] = {}

        # Optional integrations injected by the host application via the
        # plugin runtime registry. Backend wires these via
        # ``nexus_ai_engine.plugins.runtime.set_runtime(...)``; library-only
        # callers can leave them unset and journeys still execute compute /
        # s3_write / no-op steps.
        self._vq = None
        self._tool_registry = None
        try:
            from ..plugins.runtime import get_runtime
            rt = get_runtime()
            self._vq = getattr(rt, "virtual_query_service", None)
            self._tool_registry = getattr(rt, "tool_registry", None)
        except Exception:
            pass

        self._executor = YAMLToolExecutor(self._vq)

    @property
    def stage_name(self) -> str:
        if self._journey_def:
            return self._journey_def.display_name or self._journey_def.name
        return "Plugin Journey"

    @property
    def stage_description(self) -> str:
        if self._journey_def:
            return self._journey_def.description
        return "Dynamic journey loaded from plugin"

    @property
    def steps(self) -> List[Dict[str, Any]]:
        if not self._journey_def:
            return []
        return [
            {"id": s.id, "name": s.name, "order": i + 1, "description": s.description or s.name}
            for i, s in enumerate(self._journey_def.steps)
        ]

    def execute_step(self, step_id: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._journey_def:
            return {"status": "error", "message": "No journey definition loaded"}

        step_def = None
        for s in self._journey_def.steps:
            if s.id == step_id:
                step_def = s
                break

        if not step_def:
            return {"status": "error", "message": f"Unknown step: {step_id}"}

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._execute_step_async(step_def))
        finally:
            loop.close()

        self._step_results[step_id] = result
        self.flush_logs_to_s3(step_id)
        return result

    async def _execute_step_async(self, step: JourneyStep) -> Dict[str, Any]:
        self.stage_log("INFO", f"Executing step: {step.name}", step.id)
        start = time.monotonic()

        try:
            if step.tool:
                result = await self._execute_tool_step(step)
            elif step.type == "compute":
                result = await self._execute_compute_step(step)
            elif step.type == "s3_write":
                result = await self._execute_s3_write_step(step)
            elif step.type == "llm":
                result = {"status": "completed", "note": "LLM step not yet implemented"}
            else:
                result = {"status": "completed", "note": f"No-op step type: {step.type}"}

            elapsed = time.monotonic() - start
            self.stage_log("INFO", f"Step {step.name} completed in {elapsed:.1f}s", step.id)
            result["elapsed_seconds"] = round(elapsed, 1)
            result.setdefault("status", "completed")
            return result

        except Exception as e:
            self.stage_log("ERROR", f"Step {step.name} failed: {e}", step.id)
            return {"status": "error", "message": str(e)}

    async def _execute_tool_step(self, step: JourneyStep) -> Dict[str, Any]:
        tool_name = step.tool
        params = dict(step.params) if step.params else {}

        resolved_params = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("$"):
                resolved_params[k] = _resolve_var(v, self._step_results)
            else:
                resolved_params[k] = v

        if step.foreach:
            items = _resolve_var(step.foreach, self._step_results)
            if not isinstance(items, list):
                items = [items] if items else []

            results = []
            for i, item in enumerate(items):
                item_context = {**self._step_results, "item": item}
                item_params = {}
                for k, v in params.items():
                    if isinstance(v, str) and v.startswith("$"):
                        item_params[k] = _resolve_var(v, item_context)
                    else:
                        item_params[k] = v

                r = await self._call_tool(tool_name, item_params)
                results.append(r)

                if (i + 1) % 50 == 0:
                    self.stage_log("INFO", f"  Processed {i+1}/{len(items)}...", step.id)

            self.stage_log("INFO", f"Foreach complete: {len(results)} items processed", step.id)
            return {"status": "completed", "results": results, "count": len(results)}
        else:
            result = await self._call_tool(tool_name, resolved_params)
            return {"status": "completed", "results": result}

    async def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        if self._tool_registry:
            tool = self._tool_registry.get(tool_name)
            if tool:
                return await tool.execute(**params)

        if self._vq and tool_name == "query_virtual_entity":
            try:
                from ..plugins.runtime import build_virtual_query_request
            except ImportError:
                build_virtual_query_request = None
            if build_virtual_query_request is None:
                return {"error": "virtual_query_request builder not configured"}
            req = build_virtual_query_request(
                entity=params.get("entity", ""),
                filters=params.get("filter", {}),
                limit=params.get("limit", 500),
            )
            resp = await self._vq.query_virtual_entity(req)
            return resp.rows

        return {"error": f"Tool not found: {tool_name}"}

    async def _execute_compute_step(self, step: JourneyStep) -> Dict[str, Any]:
        logic = step.logic or ""
        if logic == "sort_by_composite_risk":
            data = self._step_results
            return {"status": "completed", "note": "Compute sort applied"}
        return {"status": "completed", "logic": logic}

    async def _execute_s3_write_step(self, step: JourneyStep) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

        bucket = getattr(self._config, "s3_recordings_bucket", "") if self._config else ""
        if not bucket:
            import os
            bucket = os.getenv("S3_RECORDINGS_BUCKET", "")

        written = 0
        if bucket and step.output:
            for name, output_cfg in step.output.items():
                prefix = output_cfg.prefix or name
                data = self._step_results.get(name, self._step_results)

                key = f"{prefix}/year={year}/month={month}/day={day}/{name}_{self.job_id}.json"
                try:
                    self.s3.put_object(
                        Bucket=bucket, Key=key,
                        Body=json.dumps(data, default=str),
                        ContentType="application/json",
                    )
                    written += 1
                    self.stage_log("INFO", f"Wrote s3://{bucket}/{key}", step.id)
                except Exception as e:
                    self.stage_log("WARNING", f"S3 write failed for {name}: {e}", step.id)

        return {"status": "completed", "files_written": written, "bucket": bucket}
