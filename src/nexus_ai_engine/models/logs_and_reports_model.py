"""
Pydantic Models for Logs and Reports Management MCP Tool

This module defines all data models for logs and reports management operations.
Models provide validation, serialization, and type safety for the logs_and_reports_tool.
"""

from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, model_validator
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class LogsAndReportsAction(str, Enum):
    """Supported logs and reports management actions"""
    
    # Log Operations
    GET_JOB_LOGS = "get_job_logs"
    ADD_LOG_ENTRY = "add_log_entry"
    SEARCH_LOGS = "search_logs"
    GET_LOGS_BY_LEVEL = "get_logs_by_level"
    EXPORT_JOB_LOGS = "export_job_logs"
    GET_ERROR_SUMMARY = "get_error_summary"
    LIST_AVAILABLE_LOGS = "list_available_logs"
    
    # Report Operations
    GET_JOB_REPORTS = "get_job_reports"
    CREATE_JOB_REPORT = "create_job_report"
    GENERATE_SUMMARY_REPORT = "generate_summary_report"
    GENERATE_PERFORMANCE_REPORT = "generate_performance_report"
    GENERATE_ERROR_ANALYSIS_REPORT = "generate_error_analysis_report"
    LIST_AVAILABLE_REPORTS = "list_available_reports"
    EXPORT_REPORTS = "export_reports"
    
    # Analysis Operations
    ANALYZE_JOB_PERFORMANCE = "analyze_job_performance"
    ANALYZE_ERROR_PATTERNS = "analyze_error_patterns"


class LogLevel(str, Enum):
    """Log level values"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExportFormat(str, Enum):
    """Export file formats"""
    JSON = "json"
    CSV = "csv"
    TXT = "txt"
    HTML = "html"


class ReportType(str, Enum):
    """Report types"""
    SUMMARY = "summary"
    PERFORMANCE = "performance"
    ERROR_ANALYSIS = "error_analysis"
    CUSTOM = "custom"
    TIMELINE = "timeline"
    METRICS = "metrics"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class LogsAndReportsActionRequest(BaseModel):
    """Main request model for logs and reports management actions"""
    
    # Required field
    action: LogsAndReportsAction = Field(..., description="Action to perform")
    
    # Common parameters
    journey_id: Optional[str] = Field(None, description="Journey ID")
    job_id: Optional[str] = Field(None, description="Job ID")
    stage_name: Optional[str] = Field(None, description="Stage name")
    step_name: Optional[str] = Field(None, description="Step name")
    
    # Log operation parameters
    log_level: Optional[Union[str, LogLevel]] = Field(None, description="Log level filter")
    log_message: Optional[str] = Field(None, description="Log message (for add_log_entry)")
    search_query: Optional[str] = Field(None, description="Search query for logs")
    log_source: Optional[str] = Field("system", description="Log source")
    log_details: Optional[Dict[str, Any]] = Field(None, description="Additional log details")
    
    # Report operation parameters
    report_type: Optional[Union[str, ReportType]] = Field(None, description="Type of report")
    report_title: Optional[str] = Field(None, description="Report title")
    report_content: Optional[Dict[str, Any]] = Field(None, description="Report content data")
    report_summary: Optional[str] = Field(None, description="Report summary")
    
    # Export parameters
    output_file: Optional[str] = Field(None, description="Export file path")
    export_format: Optional[Union[str, ExportFormat]] = Field(ExportFormat.JSON, description="Export format")
    
    # Filter parameters
    level_filter: Optional[str] = Field(None, description="Filter logs by level")
    step_filter: Optional[str] = Field(None, description="Filter logs by step")
    start_time: Optional[str] = Field(None, description="Start time filter (ISO 8601)")
    end_time: Optional[str] = Field(None, description="End time filter (ISO 8601)")
    
    # Pagination and limits
    limit: int = Field(100, ge=1, le=1000, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")
    
    class Config:
        use_enum_values = True
    
    @model_validator(mode='after')
    def validate_action_parameters(self):
        """Validate required parameters based on action"""
        action = self.action
        journey_id = self.journey_id
        job_id = self.job_id
        stage_name = self.stage_name
        step_name = self.step_name
        
        # Actions requiring journey_id
        journey_required_actions = [
            LogsAndReportsAction.GET_JOB_LOGS,
            LogsAndReportsAction.ADD_LOG_ENTRY,
            LogsAndReportsAction.SEARCH_LOGS,
            LogsAndReportsAction.GET_LOGS_BY_LEVEL,
            LogsAndReportsAction.EXPORT_JOB_LOGS,
            LogsAndReportsAction.GET_ERROR_SUMMARY,
            LogsAndReportsAction.LIST_AVAILABLE_LOGS,
            LogsAndReportsAction.GET_JOB_REPORTS,
            LogsAndReportsAction.CREATE_JOB_REPORT,
            LogsAndReportsAction.GENERATE_SUMMARY_REPORT,
            LogsAndReportsAction.GENERATE_PERFORMANCE_REPORT,
            LogsAndReportsAction.GENERATE_ERROR_ANALYSIS_REPORT,
            LogsAndReportsAction.EXPORT_REPORTS,
            LogsAndReportsAction.ANALYZE_JOB_PERFORMANCE,
            LogsAndReportsAction.ANALYZE_ERROR_PATTERNS,
        ]
        
        if action in journey_required_actions and not journey_id:
            raise ValueError(f"journey_id is required for action '{action}'")
        
        # Actions requiring job_id
        job_required_actions = [
            LogsAndReportsAction.GET_JOB_LOGS,
            LogsAndReportsAction.ADD_LOG_ENTRY,
            LogsAndReportsAction.EXPORT_JOB_LOGS,
            LogsAndReportsAction.GET_JOB_REPORTS,
            LogsAndReportsAction.CREATE_JOB_REPORT,
            LogsAndReportsAction.GENERATE_SUMMARY_REPORT,
            LogsAndReportsAction.GENERATE_PERFORMANCE_REPORT,
            LogsAndReportsAction.GENERATE_ERROR_ANALYSIS_REPORT,
            LogsAndReportsAction.EXPORT_REPORTS,
            LogsAndReportsAction.ANALYZE_JOB_PERFORMANCE,
        ]
        
        if action in job_required_actions and not job_id:
            raise ValueError(f"job_id is required for action '{action}'")
        
        # Actions requiring stage_name
        stage_required_actions = [
            LogsAndReportsAction.GET_JOB_LOGS,
            LogsAndReportsAction.ADD_LOG_ENTRY,
        ]
        
        if action in stage_required_actions and not stage_name:
            raise ValueError(f"stage_name is required for action '{action}'")
        
        # Validate ADD_LOG_ENTRY parameters
        if action == LogsAndReportsAction.ADD_LOG_ENTRY:
            if not step_name:
                raise ValueError("step_name is required for ADD_LOG_ENTRY action")
            if not self.log_level:
                raise ValueError("log_level is required for ADD_LOG_ENTRY action")
            if not self.log_message:
                raise ValueError("log_message is required for ADD_LOG_ENTRY action")
        
        # Validate SEARCH_LOGS parameters
        if action == LogsAndReportsAction.SEARCH_LOGS:
            if not self.search_query:
                raise ValueError("search_query is required for SEARCH_LOGS action")
        
        # Validate GET_LOGS_BY_LEVEL parameters
        if action == LogsAndReportsAction.GET_LOGS_BY_LEVEL:
            if not self.log_level:
                raise ValueError("log_level is required for GET_LOGS_BY_LEVEL action")
        
        # Validate EXPORT_JOB_LOGS parameters
        if action == LogsAndReportsAction.EXPORT_JOB_LOGS:
            if not self.output_file:
                raise ValueError("output_file is required for EXPORT_JOB_LOGS action")
        
        # Validate CREATE_JOB_REPORT parameters
        if action == LogsAndReportsAction.CREATE_JOB_REPORT:
            if not self.report_type:
                raise ValueError("report_type is required for CREATE_JOB_REPORT action")
            if not self.report_title:
                raise ValueError("report_title is required for CREATE_JOB_REPORT action")
            if not self.report_content:
                raise ValueError("report_content is required for CREATE_JOB_REPORT action")
        
        # Validate EXPORT_REPORTS parameters
        if action == LogsAndReportsAction.EXPORT_REPORTS:
            if not self.output_file:
                raise ValueError("output_file is required for EXPORT_REPORTS action")
        
        return self


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class LogsAndReportsResponse(BaseModel):
    """Standard response model for logs and reports operations"""
    status: Literal["success", "error"] = Field(..., description="Operation status")
    message: str = Field(..., description="Human-readable message")
    operation: str = Field(..., description="Operation performed")
    data: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(None, description="Response data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    error_code: Optional[str] = Field(None, description="Error code if status is error")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if status is error")
    timestamp: Optional[str] = Field(None, description="Response timestamp (ISO 8601)")
    
    class Config:
        json_encoders = {
            # Handle any custom serialization if needed
        }


class LogEntry(BaseModel):
    """Log entry structure"""
    jobId: str = Field(..., description="Job ID")
    timestamp: str = Field(..., description="Log timestamp (ISO 8601)")
    level: str = Field(..., description="Log level")
    step: str = Field(..., description="Step name")
    message: str = Field(..., description="Log message")
    source: Optional[str] = Field("system", description="Log source")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional details")


class LogSummary(BaseModel):
    """Log summary statistics"""
    jobId: str = Field(..., description="Job ID")
    stageId: Optional[str] = Field(None, description="Stage ID")
    totalLogs: int = Field(0, description="Total log entries")
    errorCount: int = Field(0, description="Error count")
    warningCount: int = Field(0, description="Warning count")
    infoCount: int = Field(0, description="Info count")
    debugCount: int = Field(0, description="Debug count")
    steps: Optional[List[str]] = Field(default_factory=list, description="Steps with logs")
    firstEntry: Optional[str] = Field(None, description="First log timestamp")
    lastEntry: Optional[str] = Field(None, description="Last log timestamp")


class ReportMetadata(BaseModel):
    """Report metadata structure"""
    reportId: str = Field(..., description="Report ID")
    jobId: str = Field(..., description="Job ID")
    reportType: str = Field(..., description="Report type")
    title: str = Field(..., description="Report title")
    summary: str = Field(..., description="Report summary")
    generatedAt: str = Field(..., description="Generation timestamp (ISO 8601)")
    status: str = Field("generated", description="Report status")


class ErrorSummary(BaseModel):
    """Error summary structure"""
    journeyId: str = Field(..., description="Journey ID")
    jobId: Optional[str] = Field(None, description="Job ID (if specific)")
    totalErrors: int = Field(0, description="Total error count")
    totalWarnings: int = Field(0, description="Total warning count")
    errorCategories: Dict[str, int] = Field(default_factory=dict, description="Errors by category")
    errorsByStep: Dict[str, int] = Field(default_factory=dict, description="Errors by step")
    recentErrors: List[LogEntry] = Field(default_factory=list, description="Recent errors")
    recentWarnings: List[LogEntry] = Field(default_factory=list, description="Recent warnings")
    generatedAt: str = Field(..., description="Generation timestamp (ISO 8601)")


class PerformanceReport(BaseModel):
    """Performance report structure"""
    reportId: str = Field(..., description="Report ID")
    jobId: str = Field(..., description="Job ID")
    reportType: str = Field("performance_analysis", description="Report type")
    generatedAt: str = Field(..., description="Generation timestamp (ISO 8601)")
    executionSummary: Dict[str, Any] = Field(..., description="Execution summary")
    performanceMetrics: Dict[str, Any] = Field(..., description="Performance metrics")
    logAnalysis: Dict[str, Any] = Field(..., description="Log analysis")
    resourceUsage: Dict[str, Any] = Field(default_factory=dict, description="Resource usage")
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="Recommendations")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_success_response(
    operation: str,
    message: str,
    data: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response following Rule 9.1.
    
    Args:
        operation: Operation name
        message: Success message
        data: Response data
        metadata: Additional metadata
        timestamp: Response timestamp
        
    Returns:
        Standardized success response dict
    """
    from datetime import datetime, timezone
    
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    response = {
        "result": {
            "status": "success",
            "message": message,
            "operation": operation,
            "data": data
        },
        "timestamp": timestamp
    }
    
    if metadata:
        response["result"]["metadata"] = metadata
    
    return response


def create_error_response(
    operation: str,
    message: str,
    error_code: str = "INTERNAL_ERROR",
    error_details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response following Rule 9.1.
    
    Args:
        operation: Operation name
        message: Error message
        error_code: Error code
        error_details: Error details
        timestamp: Response timestamp
        
    Returns:
        Standardized error response dict
    """
    from datetime import datetime, timezone
    
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    response = {
        "result": {
            "status": "error",
            "message": message,
            "operation": operation,
            "error_code": error_code
        },
        "timestamp": timestamp
    }
    
    if error_details:
        response["result"]["error_details"] = error_details
    
    return response

