"""ToolRuntime factory — injected into every tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from nexus_tool_sdk.connector_client import ConnectorClient
from nexus_tool_sdk.context import ExecutionContext
from nexus_tool_sdk.vdl_client import VdlClient


@dataclass
class ToolRuntime:
    """Credential-blind runtime for tool execution in AI Engine workers."""

    vdl: VdlClient
    connectors: ConnectorClient
    context: ExecutionContext
    ontology_base_url: str

    @classmethod
    def create(
        cls,
        *,
        context: ExecutionContext,
        vdl_base_url: str,
        connector_base_url: str,
        http: httpx.AsyncClient | None = None,
        ontology_base_url: str | None = None,
    ) -> ToolRuntime:
        client = http or httpx.AsyncClient(timeout=60.0)
        base = ontology_base_url or vdl_base_url.rsplit("/vdl", 1)[0]
        return cls(
            vdl=VdlClient(vdl_base_url, client, context),
            connectors=ConnectorClient(connector_base_url, client, context),
            context=context,
            ontology_base_url=base,
        )
