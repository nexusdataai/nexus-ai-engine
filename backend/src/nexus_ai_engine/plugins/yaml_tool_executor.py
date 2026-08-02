"""
YAML Tool Executor

Interprets declarative tool definitions from YAML and executes them
against the Virtual Data Layer. Supports variable interpolation,
virtual queries, comparisons, and aggregations.
"""

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from .plugin_models import ToolDefinition

exec_logger = logger.bind(component="yaml-tool-executor")


def _resolve_var(expr: str, context: Dict[str, Any]) -> Any:
    """Resolve a variable expression like $order.Amount or $deliveries[0].Delivery_ID."""
    if not isinstance(expr, str) or not expr.startswith("$"):
        return expr

    path = expr[1:]

    func_match = re.match(r"^(\w+)\((.+)\)$", path)
    if func_match:
        func_name, inner = func_match.groups()
        inner_val = _resolve_var(f"${inner}", context)
        if func_name == "sum" and isinstance(inner_val, list):
            return sum(float(v) for v in inner_val if v is not None)
        if func_name == "count" and isinstance(inner_val, list):
            return len(inner_val)
        if func_name == "avg" and isinstance(inner_val, list):
            vals = [float(v) for v in inner_val if v is not None]
            return sum(vals) / len(vals) if vals else 0
        return inner_val

    parts = re.split(r"\.|\[", path)
    current = context
    for part in parts:
        part = part.rstrip("]")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            except (ValueError, IndexError):
                if part and isinstance(current, list) and current:
                    current = [item.get(part) if isinstance(item, dict) else None for item in current]
                else:
                    return None
        else:
            return None
        if current is None:
            return None
    return current


def _resolve_params(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve all variable references in a params dict."""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("$"):
            resolved[k] = _resolve_var(v, context)
        elif isinstance(v, dict):
            resolved[k] = _resolve_params(v, context)
        else:
            resolved[k] = v
    return resolved


class YAMLToolExecutor:
    """Executes declarative tool definitions against the Virtual Data Layer."""

    def __init__(self, virtual_query_service=None):
        self._vq = virtual_query_service

    async def execute(self, tool_def: ToolDefinition, arguments: Dict[str, Any]) -> Dict[str, Any]:
        impl = tool_def.implementation
        if impl.type == "virtual_query_pipeline":
            return await self._execute_pipeline(impl.steps, arguments)
        elif impl.type == "python_handler":
            return {"error": "python_handler not supported in YAML executor", "tool": tool_def.name}
        else:
            return {"error": f"Unknown implementation type: {impl.type}", "tool": tool_def.name}

    async def _execute_pipeline(self, steps: List[Dict[str, Any]], arguments: Dict[str, Any]) -> Dict[str, Any]:
        context: Dict[str, Any] = {**arguments}

        for step in steps:
            output_key = step.get("output", "")

            if "query" in step:
                result = await self._exec_query(step["query"], context)
                if output_key:
                    context[output_key] = result

            elif "compare" in step:
                result = self._exec_compare(step["compare"], context)
                if output_key:
                    context[output_key] = result

            elif "aggregate" in step:
                result = self._exec_aggregate(step["aggregate"], context)
                if output_key:
                    context[output_key] = result

            elif "transform" in step:
                result = self._exec_transform(step["transform"], context)
                if output_key:
                    context[output_key] = result

        return context

    async def _exec_query(self, query_spec: Dict[str, Any], context: Dict[str, Any]) -> Any:
        if not self._vq:
            return []

        entity = query_spec.get("entity", "")
        raw_filter = query_spec.get("filter", {})
        limit = query_spec.get("limit", 100)

        resolved_filter = _resolve_params(raw_filter, context)

        try:
            from .runtime import build_virtual_query_request
        except ImportError:
            build_virtual_query_request = None
        if build_virtual_query_request is None:
            exec_logger.warning("virtual_query_request builder not configured; skipping query")
            return []

        req = build_virtual_query_request(entity=entity, filters=resolved_filter, limit=limit)
        try:
            resp = await self._vq.query_virtual_entity(req)
            return resp.rows
        except Exception as e:
            exec_logger.warning(f"Query {entity} failed: {e}")
            return []

    def _exec_compare(self, compare_spec: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        tolerance = compare_spec.get("tolerance", {})
        fields = {k: v for k, v in compare_spec.items() if k not in ("tolerance", "output")}

        resolved = {}
        for name, expr in fields.items():
            resolved[name] = _resolve_var(expr, context) if isinstance(expr, str) and expr.startswith("$") else expr

        discrepancies = []
        values = list(resolved.values())
        numeric_vals = [float(v) for v in values if v is not None and isinstance(v, (int, float))]

        if len(numeric_vals) >= 2:
            base = numeric_vals[0]
            for i, val in enumerate(numeric_vals[1:], 1):
                if base > 0:
                    pct_diff = abs(val - base) / base
                    tol_key = list(tolerance.keys())[min(i - 1, len(tolerance) - 1)] if tolerance else "default"
                    tol_val = list(tolerance.values())[min(i - 1, len(tolerance) - 1)] if tolerance else 0.05
                    if pct_diff > tol_val:
                        discrepancies.append(f"{list(resolved.keys())[i]} differs by {pct_diff:.1%} (tolerance {tol_val:.0%})")

        return {
            "match_status": "matched" if not discrepancies else "mismatch",
            "values": resolved,
            "discrepancies": discrepancies,
        }

    def _exec_aggregate(self, agg_spec: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for name, expr in agg_spec.items():
            result[name] = _resolve_var(expr, context) if isinstance(expr, str) and expr.startswith("$") else expr
        return result

    def _exec_transform(self, transform_spec: Dict[str, Any], context: Dict[str, Any]) -> Any:
        op = transform_spec.get("operation", "")
        source = _resolve_var(transform_spec.get("source", ""), context)

        if op == "sort" and isinstance(source, list):
            key = transform_spec.get("key", "")
            reverse = transform_spec.get("reverse", False)
            return sorted(source, key=lambda x: x.get(key, 0) if isinstance(x, dict) else 0, reverse=reverse)
        if op == "filter" and isinstance(source, list):
            field = transform_spec.get("field", "")
            value = transform_spec.get("value")
            return [item for item in source if isinstance(item, dict) and item.get(field) == value]

        return source
