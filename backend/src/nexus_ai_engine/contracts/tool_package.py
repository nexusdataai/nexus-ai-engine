"""Tool package manifest (docs/spec/040)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nexus_ai_engine.contracts.journey_dsl import RiskClass


class ToolPackageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    domain: str = Field(min_length=1, max_length=64)
    publisher: str = Field(min_length=1, max_length=128)


class OntologyApiSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vdl_base_url: str
    connector_base_url: str


class ToolPackageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    module: str = Field(min_length=1, description="Python import path module:ClassName")
    risk_class: RiskClass = RiskClass.READ
    requires_approval: bool = False


class ToolPackageProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_suite: str | None = None
    test_report_uri: str | None = None
    git_sha: str | None = None


class ToolPackageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_api: OntologyApiSpec
    tools: list[ToolPackageEntry] = Field(min_length=1)
    provenance: ToolPackageProvenance | None = None


class ToolPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_version: str = Field(alias="apiVersion", default="nexus.ai/v1")
    kind: str = Field(default="ToolPackage")
    metadata: ToolPackageMetadata
    spec: ToolPackageSpec
