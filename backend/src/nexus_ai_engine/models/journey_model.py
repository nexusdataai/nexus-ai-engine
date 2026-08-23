"""
Pydantic Models for Journey Management MCP Tool

This module defines all data models for journey, stage, and rule management operations.
Models provide validation, serialization, and type safety for the journey MCP tool.
"""

from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class JourneyAction(str, Enum):
    """Supported journey management actions"""
    # Journey CRUD
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    
    # Stage Management
    LIST_STAGES = "list_stages"
    ADD_STAGE = "add_stage"
    UPDATE_STAGE = "update_stage"
    DELETE_STAGE = "delete_stage"
    ADD_DEFAULT_STAGES = "add_default_stages"
    
    # Rule Management
    LIST_RULES = "list_rules"
    ADD_RULE = "add_rule"
    UPDATE_RULE = "update_rule"
    DELETE_RULE = "delete_rule"
    
    # Journey Utilities
    EXPORT_COMPLETE = "export_complete"
    IMPORT_COMPLETE = "import_complete"
    DASHBOARD = "dashboard"
    GET_JOURNEY_SUMMARY = "get_journey_summary"
    GET_COMPREHENSIVE = "get_comprehensive"
    CLEAN_ALL = "clean_all"
    
    # Job Utilities
    RUN_JOB = "run_job"
    UPDATE_JOB_STATUS = "update_job_status"
    GET_JOB_METRICS = "get_job_metrics"
    GET_JOB_TIMELINE = "get_job_timeline"
    BATCH_CANCEL_JOBS = "batch_cancel_jobs"
    GET_AGGREGATE_REPORT = "get_aggregate_report"


class JourneyStatus(str, Enum):
    """Journey status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class Priority(str, Enum):
    """Priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleType(str, Enum):
    """Second Brain rule types"""
    FIELD_MAPPING = "field_mapping"
    CONTEXTUAL_RECOMMENDATIONS = "contextual_recommendations"
    DATA_INTERPRETATION = "data_interpretation"
    VALIDATION_RULES = "validation_rules"
    BUSINESS_LOGIC = "business_logic"
    COMPLIANCE_CHECK = "compliance_check"


class RuleScope(str, Enum):
    """Rule scope levels"""
    GLOBAL = "global"
    PROJECT = "project"
    STAGE = "stage"


class RuleStatus(str, Enum):
    """Rule status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class StageId(str, Enum):
    """Available stage IDs"""
    RAW_ANALYSIS = "raw_analysis"
    STRIPPED_SCHEMA = "stripped_schema"
    TMF_MAPPING = "tmf_mapping"
    MIGRATION_PLANNING = "migration_planning"
    DATA_MIGRATION = "data_migration"
    VERIFICATION_VALIDATION = "verification_validation"


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# DATA MODELS
# =============================================================================

class StageDefinition(BaseModel):
    """Stage definition for journey creation (simplified, before StageData is defined)"""
    stageId: str = Field(..., description="Stage identifier")
    name: str = Field(..., description="Stage name")
    description: Optional[str] = Field(None, description="Stage description")
    order: int = Field(1, description="Stage order in sequence")
    secondBrainEnabled: bool = Field(True, description="Enable Second Brain AI")
    estimatedDuration: Optional[str] = Field("30m", description="Estimated duration")
    status: Optional[str] = Field("pending", description="Stage status")
    steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Stage steps")
    dependencies: Optional[List[str]] = Field(default_factory=list, description="Dependent stages")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Stage configuration")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        use_enum_values = True


class JourneyData(BaseModel):
    """Journey metadata structure"""
    name: str = Field(..., description="Journey name")
    description: Optional[str] = Field(None, description="Journey description")
    odaComponentType: str = Field(..., description="ODA component type")
    priority: Optional[Priority] = Field(Priority.MEDIUM, description="Journey priority")
    status: Optional[JourneyStatus] = Field(JourneyStatus.PENDING, description="Journey status")
    createdBy: Optional[str] = Field("system", description="Creator identifier")
    tags: Optional[List[str]] = Field(default_factory=list, description="Journey tags")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    stages: Optional[List[StageDefinition]] = Field(None, description="Stages to create with journey (required for create)")
    
    class Config:
        use_enum_values = True


class StageData(BaseModel):
    """Stage definition structure"""
    stageId: str = Field(..., description="Stage identifier")
    name: str = Field(..., description="Stage name")
    description: Optional[str] = Field(None, description="Stage description")
    order: int = Field(..., description="Stage order in sequence")
    secondBrainEnabled: bool = Field(True, description="Enable Second Brain AI")
    estimatedDuration: Optional[str] = Field("30m", description="Estimated duration")
    status: Optional[str] = Field("pending", description="Stage status")
    steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Stage steps")
    dependencies: Optional[List[str]] = Field(default_factory=list, description="Dependent stages")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        use_enum_values = True


class RuleData(BaseModel):
    """Second Brain rule structure"""
    title: str = Field(..., description="Rule title")
    description: str = Field(..., description="Rule description")
    type: RuleType = Field(..., description="Rule type")
    priority: Priority = Field(Priority.MEDIUM, description="Rule priority")
    scope: RuleScope = Field(RuleScope.STAGE, description="Rule scope")
    status: RuleStatus = Field(RuleStatus.ACTIVE, description="Rule status")
    context: str = Field(..., description="Rule context (required)")
    content: str = Field(..., description="Rule content/prompt (required)")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule conditions")
    actions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule actions")
    examples: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Rule examples")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        use_enum_values = True


class JobStatusUpdate(BaseModel):
    """Job status update data"""
    status: JobStatus = Field(..., description="New job status")
    progress: Optional[int] = Field(None, ge=0, le=100, description="Progress percentage")
    current_step: Optional[str] = Field(None, description="Current execution step")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        use_enum_values = True


# =============================================================================
# REQUEST MODELS
# =============================================================================

class JourneyActionRequest(BaseModel):
    """Main request model for journey management actions"""
    
    # Required field
    action: JourneyAction = Field(..., description="Action to perform")
    
    # Common parameters
    journey_id: Optional[str] = Field(None, description="Journey ID")
    stage_id: Optional[str] = Field(None, description="Stage ID")
    rule_id: Optional[str] = Field(None, description="Rule ID")
    job_id: Optional[str] = Field(None, description="Job ID")
    
    # Journey creation/update parameters
    name: Optional[str] = Field(None, description="Journey name (for create/update)")
    description: Optional[str] = Field(None, description="Journey description (for create/update)")
    odaComponentType: Optional[str] = Field(None, description="Component type (for create/update)")
    priority: Optional[str] = Field(None, description="Journey priority (for create/update)")
    status: Optional[str] = Field(None, description="Journey status (for create/update)")
    estimatedDuration: Optional[str] = Field(None, description="Estimated duration (for create/update)")
    tags: Optional[List[str]] = Field(None, description="Journey tags (for create/update)")
    version: Optional[str] = Field(None, description="Journey version (for create/update)")
    lastModified: Optional[str] = Field(None, description="Last modified timestamp (for create/update)")
    journey_data: Optional[Union[Dict[str, Any], JourneyData]] = Field(None, description="Journey data dict")
    
    # Stage parameters
    stage_data: Optional[Union[Dict[str, Any], StageData]] = Field(None, description="Stage data dict")
    
    # Rule parameters
    rule_data: Optional[Union[Dict[str, Any], RuleData]] = Field(None, description="Rule data dict")
    rule_type: Optional[RuleType] = Field(None, description="Filter by rule type")
    
    # Filter parameters
    status_filter: Optional[Union[str, JourneyStatus]] = Field(None, description="Filter by status")
    component_type_filter: Optional[str] = Field(None, description="Filter by component type")
    
    # Options
    include_all: bool = Field(False, description="Include all details")
    confirm: bool = Field(False, description="Skip confirmation prompts")
    
    # Job-related parameters
    job_status: Optional[JobStatus] = Field(None, description="Job status for updates")
    progress: Optional[int] = Field(None, ge=0, le=100, description="Job progress percentage")
    current_step: Optional[str] = Field(None, description="Current step for job updates")
    error_message: Optional[str] = Field(None, description="Error message for job updates")
    job_ids: Optional[List[str]] = Field(None, description="List of job IDs for batch operations")
    reason: Optional[str] = Field(None, description="Reason for operation")
    triggered_by: Optional[str] = Field(None, description="Who triggered the job execution")
    
    # Import/Export parameters
    output_file: Optional[str] = Field(None, description="Output file for export")
    input_file: Optional[str] = Field(None, description="Input file for import")
    new_journey_id: Optional[str] = Field(None, description="New journey ID for import")
    
    class Config:
        use_enum_values = True
    
    @model_validator(mode='after')
    def validate_action_parameters(self):
        """Validate required parameters based on action"""
        action = self.action
        journey_id = self.journey_id
        stage_id = self.stage_id
        rule_id = self.rule_id
        job_id = self.job_id
        
        # Actions requiring journey_id
        journey_required_actions = [
            JourneyAction.READ,
            JourneyAction.UPDATE,
            JourneyAction.DELETE,
            JourneyAction.LIST_STAGES,
            JourneyAction.ADD_STAGE,
            JourneyAction.UPDATE_STAGE,
            JourneyAction.DELETE_STAGE,
            JourneyAction.ADD_DEFAULT_STAGES,
            JourneyAction.LIST_RULES,
            JourneyAction.ADD_RULE,
            JourneyAction.UPDATE_RULE,
            JourneyAction.DELETE_RULE,
            JourneyAction.EXPORT_COMPLETE,
            JourneyAction.DASHBOARD,
            JourneyAction.GET_JOURNEY_SUMMARY,
            JourneyAction.GET_COMPREHENSIVE,
            JourneyAction.RUN_JOB,
            JourneyAction.UPDATE_JOB_STATUS,
            JourneyAction.GET_JOB_METRICS,
            JourneyAction.GET_JOB_TIMELINE,
            JourneyAction.BATCH_CANCEL_JOBS,
        ]
        
        if action in journey_required_actions and not journey_id:
            raise ValueError(f"journey_id is required for action '{action}'")
        
        # Actions requiring stage_id
        stage_required_actions = [
            JourneyAction.UPDATE_STAGE,
            JourneyAction.DELETE_STAGE,
            JourneyAction.ADD_RULE,
            JourneyAction.RUN_JOB,
        ]
        
        if action in stage_required_actions and not stage_id:
            raise ValueError(f"stage_id is required for action '{action}'")
        
        # Actions requiring rule_id
        if action in [JourneyAction.UPDATE_RULE, JourneyAction.DELETE_RULE] and not rule_id:
            raise ValueError(f"rule_id is required for action '{action}'")
        
        # Actions requiring job_id
        job_required_actions = [
            JourneyAction.UPDATE_JOB_STATUS,
            JourneyAction.GET_JOB_METRICS,
            JourneyAction.GET_JOB_TIMELINE,
        ]
        
        if action in job_required_actions and not job_id:
            raise ValueError(f"job_id is required for action '{action}'")
        
        # Validate CREATE action parameters
        if action == JourneyAction.CREATE:
            journey_data = self.journey_data
            name = self.name
            oda_component = self.odaComponentType
            
            # Either journey_data must be provided, or name + odaComponentType
            if not journey_data and not (name and oda_component):
                raise ValueError(
                    "For CREATE action, either journey_data or (name + odaComponentType) must be provided"
                )
            
            # Validate that at least one stage is provided
            stages = None
            if journey_data:
                if isinstance(journey_data, dict):
                    stages = journey_data.get('stages')
                elif hasattr(journey_data, 'stages'):
                    stages = journey_data.stages
            
            if not stages or len(stages) == 0:
                raise ValueError(
                    "For CREATE action, at least one stage must be provided in journey_data.stages"
                )
        
        # Validate stage data for ADD_STAGE and UPDATE_STAGE
        if action in [JourneyAction.ADD_STAGE, JourneyAction.UPDATE_STAGE]:
            if not self.stage_data:
                raise ValueError(f"stage_data is required for action '{action}'")
        
        # Validate rule data for ADD_RULE and UPDATE_RULE
        if action in [JourneyAction.ADD_RULE, JourneyAction.UPDATE_RULE]:
            if not self.rule_data:
                raise ValueError(f"rule_data is required for action '{action}'")
        
        # Validate UPDATE_JOB_STATUS parameters
        if action == JourneyAction.UPDATE_JOB_STATUS:
            if not self.job_status:
                raise ValueError("job_status is required for UPDATE_JOB_STATUS action")
        
        # Validate BATCH_CANCEL_JOBS parameters
        if action == JourneyAction.BATCH_CANCEL_JOBS:
            if not self.job_ids:
                raise ValueError("job_ids is required for BATCH_CANCEL_JOBS action")
        
        # Validate EXPORT_COMPLETE parameters
        if action == JourneyAction.EXPORT_COMPLETE:
            if not self.output_file:
                raise ValueError("output_file is required for EXPORT_COMPLETE action")
        
        # Validate IMPORT_COMPLETE parameters
        if action == JourneyAction.IMPORT_COMPLETE:
            if not self.input_file:
                raise ValueError("input_file is required for IMPORT_COMPLETE action")
        
        return self


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class JourneyResponse(BaseModel):
    """Standard response model for journey operations"""
    status: Literal["success", "error"] = Field(..., description="Operation status")
    message: str = Field(..., description="Human-readable message")
    operation: str = Field(..., description="Operation performed")
    journey_id: Optional[str] = Field(None, description="Journey ID (if applicable)")
    stage_id: Optional[str] = Field(None, description="Stage ID (if applicable)")
    rule_id: Optional[str] = Field(None, description="Rule ID (if applicable)")
    job_id: Optional[str] = Field(None, description="Job ID (if applicable)")
    data: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error details if status is error")
    error_code: Optional[str] = Field(None, description="Error code for categorizing errors")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        json_encoders = {
            # Handle any custom serialization if needed
        }


# Alias for backward compatibility and consistency with naming pattern
JourneyActionResponse = JourneyResponse


class JourneyListResponse(BaseModel):
    """Response model for list operations"""
    status: Literal["success", "error"] = Field(..., description="Operation status")
    message: str = Field(..., description="Human-readable message")
    total_count: int = Field(..., description="Total number of items")
    items: List[Dict[str, Any]] = Field(..., description="List of items")
    filters: Optional[Dict[str, str]] = Field(None, description="Applied filters")
    

class JourneySummary(BaseModel):
    """Journey summary information"""
    journey_id: str = Field(..., description="Journey ID")
    name: str = Field(..., description="Journey name")
    description: Optional[str] = Field(None, description="Journey description")
    status: str = Field(..., description="Journey status")
    priority: str = Field(..., description="Journey priority")
    odaComponentType: str = Field(..., description="ODA component type")
    overallProgress: int = Field(0, description="Overall progress percentage")
    currentStageId: Optional[str] = Field(None, description="Current stage ID")
    totalStages: int = Field(0, description="Total number of stages")
    totalRules: int = Field(0, description="Total number of rules")
    activeRules: int = Field(0, description="Active rules count")
    createdAt: Optional[str] = Field(None, description="Creation timestamp")
    updatedAt: Optional[str] = Field(None, description="Last update timestamp")
    createdBy: Optional[str] = Field(None, description="Creator identifier")


class JobMetrics(BaseModel):
    """Job execution metrics"""
    job_id: str = Field(..., description="Job ID")
    stage_id: str = Field(..., description="Stage ID")
    status: str = Field(..., description="Job status")
    progress: int = Field(0, description="Progress percentage")
    duration: Optional[float] = Field(None, description="Execution duration in seconds")
    totalLogs: int = Field(0, description="Total log entries")
    errorCount: int = Field(0, description="Error count")
    warningCount: int = Field(0, description="Warning count")
    infoCount: int = Field(0, description="Info count")
    startTime: Optional[str] = Field(None, description="Start timestamp")
    endTime: Optional[str] = Field(None, description="End timestamp")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def convert_to_journey_data(data: Union[Dict[str, Any], JourneyData]) -> Dict[str, Any]:
    """Convert JourneyData model or dict to dict"""
    if isinstance(data, JourneyData):
        return data.model_dump(exclude_none=True)
    return data


def convert_to_stage_data(data: Union[Dict[str, Any], StageData]) -> Dict[str, Any]:
    """Convert StageData model or dict to dict."""
    if isinstance(data, StageData):
        return data.model_dump(exclude_none=True)
    result = dict(data)
    if "stageId" not in result and "stage_id" in result:
        result["stageId"] = result["stage_id"]
    return result


def convert_to_rule_data(data: Union[Dict[str, Any], RuleData]) -> Dict[str, Any]:
    """Convert RuleData model or dict to dict"""
    if isinstance(data, RuleData):
        return data.model_dump(exclude_none=True)
    return data

