"""Canonical Tool base class for AI Engine tool packages."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from nexus_tool_sdk import ConnectorError, ToolRuntime, VdlError

from nexus_ai_engine.contracts.tool_descriptor import ToolDescriptor
from nexus_ai_engine.contracts.tool_request import (
    ToolError,
    ToolRequest,
    ToolResponse,
    ToolResponseStatus,
)


class ToolExecutionError(RuntimeError):
    """Raised when a tool cannot complete a request."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = details or {}


class Tool(ABC):
    """Base for every ReAct tool running in AI Engine workers."""

    tool_id: str
    version: str

    @abstractmethod
    def descriptor(self) -> ToolDescriptor:
        """Return the canonical ToolDescriptor."""

    @abstractmethod
    async def _dispatch(self, request: ToolRequest, runtime: ToolRuntime) -> dict[str, Any]:
        """Execute the capability using runtime.vdl / runtime.connectors."""

    async def execute(self, request: ToolRequest, runtime: ToolRuntime) -> ToolResponse:
        """Public entry: dispatch, time, and produce a ToolResponse."""
        started_at = datetime.now(timezone.utc)
        try:
            result = await asyncio.wait_for(self._dispatch(request, runtime), timeout=request.timeout_s)
            ended_at = datetime.now(timezone.utc)
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=ended_at,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=self.tool_id,
                tool_version=self.version,
                capability=request.capability,
                status=ToolResponseStatus.OK,
                result=result,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
            )
        except asyncio.TimeoutError:
            ended_at = datetime.now(timezone.utc)
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=ended_at,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=self.tool_id,
                tool_version=self.version,
                capability=request.capability,
                status=ToolResponseStatus.TIMEOUT,
                error=ToolError(code="TIMEOUT", message=f"exceeded {request.timeout_s}s", retryable=True),
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
            )
        except (VdlError, ConnectorError) as exc:
            ended_at = datetime.now(timezone.utc)
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=ended_at,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=self.tool_id,
                tool_version=self.version,
                capability=request.capability,
                status=ToolResponseStatus.ERROR,
                error=ToolError(
                    code=exc.code,
                    message=str(exc),
                    retryable=exc.retryable,
                    upstream_status=exc.status_code,
                    details=exc.details,
                ),
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
            )
        except ToolExecutionError as exc:
            ended_at = datetime.now(timezone.utc)
            return ToolResponse(
                id=uuid4(),
                version=1,
                created_at=ended_at,
                tenant_id=request.tenant_id,
                trace_id=request.trace_id,
                request_id=request.id,
                tool_id=self.tool_id,
                tool_version=self.version,
                capability=request.capability,
                status=ToolResponseStatus.ERROR,
                error=ToolError(
                    code=exc.code,
                    message=str(exc),
                    retryable=exc.retryable,
                    details=exc.details,
                ),
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
            )
