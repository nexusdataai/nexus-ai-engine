"""ToolRegistry tests (rc2 tool-registry)."""

from __future__ import annotations

import pytest
from nexus_ai_engine.contracts.tool_package import (
    OntologyApiSpec,
    ToolPackageEntry,
    ToolPackageManifest,
    ToolPackageMetadata,
    ToolPackageSpec,
)
from nexus_ai_engine.registry import ToolLoadError, ToolRegistry, load_tool_class
from nexus_ai_engine.tools.base import MockTool


def _sample_manifest() -> ToolPackageManifest:
    return ToolPackageManifest(
        metadata=ToolPackageMetadata(
            id="test-tools",
            version="1.0.0",
            domain="test",
            publisher="qa",
        ),
        spec=ToolPackageSpec(
            ontology_api=OntologyApiSpec(
                vdl_base_url="http://ontology/api/v1/vdl",
                connector_base_url="http://ontology/api/v1/connectors",
            ),
            tools=[
                ToolPackageEntry(
                    tool_id="mock",
                    version="0.1.0",
                    module="nexus_ai_engine.tools.base.mock:MockTool",
                )
            ],
        ),
    )


def test_register_and_get():
    reg = ToolRegistry()
    tool = MockTool()
    reg.register(tool, domain="test")
    assert reg.get("mock") is tool
    assert reg.get("mock", "0.1.0") is tool


def test_list_tools_filters_by_domain():
    reg = ToolRegistry()
    reg.register(MockTool(), domain="alpha")
    assert len(reg.list_tools()) == 1
    assert len(reg.list_tools(domain="alpha")) == 1
    assert reg.list_tools(domain="other") == []


def test_load_package_registers_tools():
    reg = ToolRegistry()
    count = reg.load_package(_sample_manifest())
    assert count == 1
    tool = reg.get("mock", "0.1.0")
    assert tool.tool_id == "mock"
    assert reg.list_tools(domain="test")[0].tool_id == "mock"


def test_load_tool_class_rejects_invalid_path():
    with pytest.raises(ToolLoadError):
        load_tool_class("not-a-valid-path")


def test_duplicate_register_raises():
    reg = ToolRegistry()
    reg.register(MockTool())
    with pytest.raises(ValueError):
        reg.register(MockTool())
