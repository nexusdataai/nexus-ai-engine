"""
Unified Models for REST API and MCP Tools
These models are shared between direct API calls and MCP tool operations
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

# Import existing models to extend/reuse
from .journey_model import JourneyAction, JourneyActionRequest, JourneyActionResponse, JourneyResponse


# ==========================================
# Common Models (Shared between API and MCP)
# ==========================================

class StatusEnum(str, Enum):
    """Common status values used across the system"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class PriorityEnum(str, Enum):
    """Priority levels for journeys and tasks"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResponseBase(BaseModel):
    """Base response model with standard fields for API responses"""
    success: bool = Field(description="Operation success status")
    message: str = Field(description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(ResponseBase):
    """Error response model for API errors"""
    success: bool = False
    error_code: str = Field(description="Error code for client handling")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# ==========================================
# Journey API Models (Extending existing)
# ==========================================

class JourneyCreateRequest(BaseModel):
    """Request model for creating a journey via REST API"""
    name: str = Field(..., min_length=1, max_length=200, description="Journey name")
    description: Optional[str] = Field(None, max_length=1000, description="Journey description")
    odaComponentType: str = Field(..., description="ODA component type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    priority: PriorityEnum = Field(PriorityEnum.MEDIUM, description="Journey priority")
    stages: Optional[List[Dict[str, Any]]] = Field(None, description="Journey stages")
    
    @validator("odaComponentType")
    def validate_component_type(cls, v):
        """Validate ODA component type"""
        valid_types = [
            "customer-management", "product-management", "order-management",
            "billing-management", "payment-management", "inventory-management",
            "party-management", "resource-management", "service-management",
            "data-pipeline"
        ]
        if v.lower() not in valid_types:
            raise ValueError(f"Invalid component type. Must be one of: {', '.join(valid_types)}")
        return v.lower()
    
    def to_action_request(self) -> JourneyActionRequest:
        """Convert to JourneyActionRequest for service layer"""
        return JourneyActionRequest(
            action="create",
            name=self.name,
            description=self.description,
            odaComponentType=self.odaComponentType,
            journey_data={
                "name": self.name,
                "description": self.description,
                "odaComponentType": self.odaComponentType,
                "metadata": self.metadata,
                "priority": self.priority.value,
                "stages": self.stages
            }
        )


class JourneyResponse(ResponseBase):
    """Response model for journey operations"""
    success: bool = True
    journey_id: Optional[str] = Field(None, description="Journey ID")
    data: Optional[Dict[str, Any]] = Field(None, description="Journey data")
    
    @classmethod
    def from_action_response(cls, response: JourneyActionResponse) -> "JourneyResponse":
        """Create from JourneyActionResponse"""
        return cls(
            success=response.status == "success",
            message=response.message,
            journey_id=response.journey_id,
            data=response.data
        )


class JourneyStatusResponse(ResponseBase):
    """Quick status response for journey"""
    journey_id: str
    status: StatusEnum
    progress: int = Field(ge=0, le=100, description="Progress percentage")
    current_stage: Optional[str] = None
    last_updated: datetime


class JourneyListRequest(BaseModel):
    """Request model for listing journeys"""
    status_filter: Optional[StatusEnum] = None
    component_type_filter: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    sort_by: str = Field("created_at", pattern="^(created_at|updated_at|name|status)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    
    def to_action_request(self) -> JourneyActionRequest:
        """Convert to JourneyActionRequest"""
        return JourneyActionRequest(
            action="list",
            status_filter=self.status_filter.value if self.status_filter else None,
            component_type_filter=self.component_type_filter
        )


class JourneyBatchRequest(BaseModel):
    """Request model for batch journey operations"""
    journey_ids: List[str] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., pattern="^(cancel|pause|resume|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


# ==========================================
# Analytics API Models
# ==========================================

class MetricType(str, Enum):
    """Types of metrics available"""
    PERFORMANCE = "performance"
    ERRORS = "errors"
    THROUGHPUT = "throughput"
    LATENCY = "latency"


class TimeRange(str, Enum):
    """Predefined time ranges"""
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    ONE_DAY = "24h"
    ONE_WEEK = "7d"
    ONE_MONTH = "30d"
    CUSTOM = "custom"


class AnalyticsRequest(BaseModel):
    """Request model for analytics queries"""
    metric_type: MetricType
    time_range: TimeRange = Field(TimeRange.ONE_DAY)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    aggregation: str = Field("avg", pattern="^(avg|sum|min|max|count)$")
    group_by: Optional[List[str]] = Field(None, max_items=3)
    
    @validator("end_time")
    def validate_time_range(cls, v, values):
        """Validate custom time range"""
        if values.get("time_range") == TimeRange.CUSTOM:
            if not values.get("start_time") or not v:
                raise ValueError("start_time and end_time required for custom time range")
            if values.get("start_time") >= v:
                raise ValueError("end_time must be after start_time")
        return v


class AnalyticsResponse(ResponseBase):
    """Response model for analytics data"""
    metric_type: str
    time_range: str
    data_points: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class DashboardDataRequest(BaseModel):
    """Request model for dashboard data"""
    widgets: List[str] = Field(..., min_items=1, max_items=10)
    refresh_interval: int = Field(30, ge=5, le=300, description="Refresh interval in seconds")
    include_historical: bool = Field(False)


# ==========================================
# Auth API Models
# ==========================================

class LoginRequest(BaseModel):
    """Login request model"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    remember_me: bool = Field(False)


class TokenResponse(ResponseBase):
    """Token response model"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Token expiry in seconds")
    refresh_token: Optional[str] = None


class UserProfile(BaseModel):
    """User profile model"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    last_login: Optional[datetime] = None
    created_at: datetime


# ==========================================
# Health API Models
# ==========================================

class HealthStatus(str, Enum):
    """Health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: HealthStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, Dict[str, Any]]
    version: str
    uptime_seconds: int


class ServiceHealthDetail(BaseModel):
    """Detailed health for a specific service"""
    name: str
    status: str
    latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    last_check: datetime
    dependencies: Optional[List[str]] = None


# ==========================================
# Streaming Models
# ==========================================

class StreamType(str, Enum):
    """Types of streams available"""
    LOGS = "logs"
    METRICS = "metrics"
    EVENTS = "events"


class StreamRequest(BaseModel):
    """Request model for streaming operations"""
    stream_type: StreamType
    filters: Optional[Dict[str, Any]] = None
    buffer_size: int = Field(100, ge=1, le=1000)
    include_historical: bool = Field(False)


class StreamChunk(BaseModel):
    """Stream chunk model for SSE/WebSocket"""
    sequence: int
    timestamp: datetime
    data: Any
    metadata: Optional[Dict[str, Any]] = None


# ==========================================
# Export Models
# ==========================================

class ExportFormat(str, Enum):
    """Supported export formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"


class ExportRequest(BaseModel):
    """Request model for data export"""
    export_type: ExportFormat
    data_scope: str = Field(..., pattern="^(all|filtered|selected)$")
    filters: Optional[Dict[str, Any]] = None
    selected_ids: Optional[List[str]] = None
    include_metadata: bool = Field(True)
    compress: bool = Field(False)


class ExportResponse(ResponseBase):
    """Response model for export operations"""
    export_id: str
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    record_count: int
    export_format: str
    expires_at: Optional[datetime] = None


# ==========================================
# Utility Functions for Model Conversion
# ==========================================

def convert_to_camelcase(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert snake_case keys to camelCase for frontend compatibility"""
    def to_camel(snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    
    if isinstance(data, dict):
        return {to_camel(k): convert_to_camelcase(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_camelcase(item) for item in data]
    else:
        return data


def convert_from_camelcase(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert camelCase keys to snake_case for backend processing"""
    def to_snake(camel_str):
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    if isinstance(data, dict):
        return {to_snake(k): convert_from_camelcase(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_from_camelcase(item) for item in data]
    else:
        return data
