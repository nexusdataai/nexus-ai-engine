"""Embedded tool registry with mock O2C tools for in-process rc1 tests."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def _echo(args: dict[str, Any]) -> dict[str, Any]:
    return {"message": args.get("message", "ok"), "status": "ok"}


async def _query_virtual_entity(args: dict[str, Any]) -> dict[str, Any]:
    entity = args.get("entity", "Unknown")
    limit = int(args.get("limit", 10))
    items = [{"Id": f"id-{i}", "Name": f"{entity}-{i}"} for i in range(min(limit, 3))]
    return {"entity": entity, "items": items, "count": len(items)}


async def _soql_query(args: dict[str, Any]) -> dict[str, Any]:
    return {"records": [{"Id": "001", "Name": "Account-A"}], "totalSize": 1}


async def _o2c_match(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "opportunity_id": args.get("opportunity_id"),
        "match_rate": 0.97,
        "exceptions": [],
    }


async def _s3_write_exceptions(args: dict[str, Any]) -> dict[str, Any]:
    return {"path": args.get("path"), "written": True}


_DEFAULT_TOOLS: dict[str, ToolHandler] = {
    "echo": _echo,
    "query_virtual_entity": _query_virtual_entity,
    "soql_query": _soql_query,
    "o2c_match_order_delivery_invoice": _o2c_match,
    "s3_write_exceptions": _s3_write_exceptions,
}


class EmbeddedToolRegistry:
    def __init__(self, tools: dict[str, ToolHandler] | None = None) -> None:
        self._tools = dict(_DEFAULT_TOOLS)
        if tools:
            self._tools.update(tools)

    def register(self, name: str, handler: ToolHandler) -> None:
        self._tools[name] = handler

    def has(self, name: str) -> bool:
        return name in self._tools

    async def invoke(self, tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self._tools.get(tool_id)
        if handler is None:
            raise KeyError(f"tool not registered: {tool_id}")
        return await handler(arguments)

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())
