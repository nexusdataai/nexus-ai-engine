"""
Plugin Specification Models

Pydantic models defining the plugin manifest, tool YAML, and journey YAML formats.
These are the canonical schema for the NexusAI plugin framework.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PluginStatus(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class PluginPermissions(BaseModel):
    virtual_entities: List[str] = Field(default_factory=list)
    risk_level: str = "read_only"
    max_query_limit: int = 1000


class PluginConfig(BaseModel):
    s3_output_prefix: str = ""
    glue_tables: List[str] = Field(default_factory=list)
    glue_database: str = ""


class PluginManifest(BaseModel):
    """The plugin.json manifest format."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    use_case: str = ""
    tools: Dict[str, str] = Field(default_factory=lambda: {"directory": "tools", "prefix": ""})
    journeys: Dict[str, str] = Field(default_factory=lambda: {"directory": "journeys"})
    policies: Dict[str, str] = Field(default_factory=lambda: {"directory": "policies"})
    config: PluginConfig = Field(default_factory=PluginConfig)
    permissions: PluginPermissions = Field(default_factory=PluginPermissions)


class ToolQueryStep(BaseModel):
    entity: str
    filter: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 100


class ToolCompareStep(BaseModel):
    tolerance: Dict[str, float] = Field(default_factory=dict)
    fields: Dict[str, str] = Field(default_factory=dict)


class ToolImplementationStep(BaseModel):
    query: Optional[ToolQueryStep] = None
    compare: Optional[ToolCompareStep] = None
    aggregate: Optional[Dict[str, str]] = None
    output: str = ""


class ToolImplementation(BaseModel):
    type: str = "virtual_query_pipeline"
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    """A tool YAML definition."""
    name: str
    description: str = ""
    risk_level: str = "read_only"
    category: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    implementation: ToolImplementation = Field(default_factory=ToolImplementation)


class JourneyStepOutput(BaseModel):
    prefix: str = ""
    partition: str = "year/month/day"
    format: str = "json"


class JourneyStepGlue(BaseModel):
    database: str = "analytics"
    tables: List[str] = Field(default_factory=list)


class JourneyStep(BaseModel):
    """A step within a journey definition."""
    id: str
    name: str
    description: str = ""
    tool: Optional[str] = None
    type: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    foreach: Optional[str] = None
    logic: Optional[str] = None
    output: Optional[Dict[str, JourneyStepOutput]] = None
    glue: Optional[JourneyStepGlue] = None


class JourneyDefinition(BaseModel):
    """A journey YAML definition."""
    name: str
    display_name: str = ""
    description: str = ""
    trigger: str = "manual"
    schedule: Optional[str] = None
    steps: List[JourneyStep] = Field(default_factory=list)


class PluginRecord(BaseModel):
    """Stored plugin metadata."""
    id: str
    manifest: PluginManifest
    status: PluginStatus = PluginStatus.REGISTERED
    tools: List[ToolDefinition] = Field(default_factory=list)
    journeys: List[JourneyDefinition] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    error_message: Optional[str] = None
    s3_path: Optional[str] = None
