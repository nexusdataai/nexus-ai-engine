"""In-process Tool Registry (docs/spec/040)."""

from __future__ import annotations

from nexus_ai_engine.contracts.tool_descriptor import ToolDescriptor
from nexus_ai_engine.contracts.tool_package import OntologyApiSpec, ToolPackageManifest
from nexus_ai_engine.registry.loader import instantiate_tool
from nexus_ai_engine.tools.base.tool import Tool


class ToolRegistry:
    """Runtime catalog loaded from published tool packages."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._domains: dict[str, str] = {}
        self._packages: dict[str, ToolPackageManifest] = {}
        self._ontology_by_tool: dict[str, OntologyApiSpec] = {}

    @staticmethod
    def _tool_key(tool_id: str, version: str) -> str:
        return f"{tool_id}@{version}"

    @staticmethod
    def _package_key(package_id: str, version: str) -> str:
        return f"{package_id}@{version}"

    def register(self, tool: Tool, *, domain: str | None = None) -> None:
        key = self._tool_key(tool.tool_id, tool.version)
        if key in self._tools:
            raise ValueError(f"tool already registered: {key}")
        self._tools[key] = tool
        if domain is not None:
            self._domains[key] = domain

    def get(self, tool_id: str, version: str | None = None) -> Tool:
        if version is not None:
            key = self._tool_key(tool_id, version)
            if key not in self._tools:
                raise KeyError(f"unknown tool: {key}")
            return self._tools[key]

        matching = [t for key, t in self._tools.items() if key.startswith(f"{tool_id}@")]
        if not matching:
            raise KeyError(f"unknown tool: {tool_id}")
        matching.sort(key=lambda t: t.version, reverse=True)
        return matching[0]

    def list_tools(self, domain: str | None = None) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []
        for key, tool in self._tools.items():
            if domain is not None and self._domains.get(key) != domain:
                continue
            descriptors.append(tool.descriptor())
        return sorted(descriptors, key=lambda d: d.tool_id)

    def catalog_tool_ids(self) -> frozenset[str]:
        return frozenset(tool.tool_id for tool in self._tools.values())

    def ontology_api_for(self, tool_id: str, version: str | None = None) -> OntologyApiSpec | None:
        if version is not None:
            return self._ontology_by_tool.get(self._tool_key(tool_id, version))
        matching = [
            spec
            for key, spec in self._ontology_by_tool.items()
            if key.startswith(f"{tool_id}@")
        ]
        if not matching:
            return None
        return matching[0]

    def list_packages(self) -> list[ToolPackageManifest]:
        return list(self._packages.values())

    def load_package(self, package: ToolPackageManifest) -> int:
        pkg_key = self._package_key(package.metadata.id, package.metadata.version)
        if pkg_key in self._packages:
            raise ValueError(f"package already loaded: {pkg_key}")

        registered = 0
        domain = package.metadata.domain
        for entry in package.spec.tools:
            tool = instantiate_tool(entry.module)
            if tool.tool_id != entry.tool_id:
                raise ValueError(
                    f"tool_id mismatch for {entry.module}: manifest={entry.tool_id} class={tool.tool_id}"
                )
            if tool.version != entry.version:
                raise ValueError(
                    f"version mismatch for {entry.module}: manifest={entry.version} class={tool.version}"
                )
            self.register(tool, domain=domain)
            self._ontology_by_tool[self._tool_key(entry.tool_id, entry.version)] = package.spec.ontology_api
            registered += 1

        self._packages[pkg_key] = package
        return registered
