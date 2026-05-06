"""
Logs and Reports Management MCP Tool

FastMCP tool wrapper for logs and reports management operations.
Provides comprehensive logs and reports operations accessible via MCP protocol.
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional, List, Dict, Any

from ....services.logs_and_reports_service import LogsAndReportsService
from ....models.logs_and_reports_model import LogsAndReportsActionRequest, LogsAndReportsAction


def register_logs_and_reports_tools(mcp: FastMCP):
    """
    Register logs and reports management tools with FastMCP server.
    
    Args:
        mcp: FastMCP server instance
    """
    
    @mcp.tool(
        name="logs_and_reports_tool",
        description="Comprehensive logs and reports management for TMF ODA journey jobs. Supports log retrieval, searching, filtering, report generation, performance analysis, and error pattern detection."
    )
    async def logs_and_reports_tool(
        action: str,
        journey_id: Optional[str] = None,
        job_id: Optional[str] = None,
        stage_name: Optional[str] = None,
        step_name: Optional[str] = None,
        log_level: Optional[str] = None,
        log_message: Optional[str] = None,
        search_query: Optional[str] = None,
        log_source: str = "system",
        log_details: Optional[Dict[str, Any]] = None,
        report_type: Optional[str] = None,
        report_title: Optional[str] = None,
        report_content: Optional[Dict[str, Any]] = None,
        report_summary: Optional[str] = None,
        output_file: Optional[str] = None,
        export_format: str = "json",
        level_filter: Optional[str] = None,
        step_filter: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Comprehensive logs and reports management tool for TMF ODA transformation jobs.
        
        Actions:
        
        **Log Operations:**
        - get_job_logs: Get logs for specific job
        - add_log_entry: Add log entry to job
        - search_logs: Search through logs with query
        - get_logs_by_level: Filter logs by level (error/warning/info/debug)
        - export_job_logs: Export logs to file (json/csv/txt/html)
        - get_error_summary: Get error analysis summary
        - list_available_logs: List available log sources
        
        **Report Operations:**
        - get_job_reports: Get reports for job
        - create_job_report: Create custom report
        - generate_summary_report: Generate job summary report
        - generate_performance_report: Generate performance analysis
        - generate_error_analysis_report: Generate error analysis
        - list_available_reports: List available reports
        - export_reports: Export reports to file
        
        **Analysis Operations:**
        - analyze_job_performance: Analyze performance metrics
        - analyze_error_patterns: Analyze error patterns
        
        Args:
            action: Action to perform (required)
            journey_id: Journey ID (required for most operations)
            job_id: Job ID (required for job-specific operations)
            stage_name: Stage name (required for get_job_logs, add_log_entry)
            step_name: Step name (for specific step logs)
            log_level: Log level (error/warning/info/debug)
            log_message: Log message (for add_log_entry)
            search_query: Search query string (for search_logs)
            log_source: Log source identifier (default: "system")
            log_details: Additional log details dict
            report_type: Report type (summary/performance/error_analysis/custom)
            report_title: Report title (for create_job_report)
            report_content: Report content data dict (for create_job_report)
            report_summary: Report summary text
            output_file: Output file path (for export operations)
            export_format: Export format (json/csv/txt/html, default: json)
            level_filter: Filter by log level (for search_logs)
            step_filter: Filter by step name (for search_logs)
            start_time: Start time filter (ISO 8601)
            end_time: End time filter (ISO 8601)
            limit: Result limit (default: 100, max: 1000)
            offset: Result offset (default: 0)
        
        Returns:
            Dict with standardized response following Rule 9.1:
            {
              "result": {
                "status": "success" | "error",
                "message": "Human-readable message",
                "operation": "action_name",
                "data": {...},
                "metadata": {...}
              },
              "timestamp": "ISO8601_timestamp"
            }
            
        Example Usage:
            # Get job logs
            {"action": "get_job_logs", "journey_id": "JRN-123", "job_id": "JOB-456", "stage_name": "raw_analysis"}
            
            # Search logs
            {"action": "search_logs", "journey_id": "JRN-123", "search_query": "error", "level_filter": "error"}
            
            # Generate performance report
            {"action": "generate_performance_report", "journey_id": "JRN-123", "job_id": "JOB-456"}
            
            # Get error summary
            {"action": "get_error_summary", "journey_id": "JRN-123", "job_id": "JOB-456"}
            
            # Export logs
            {"action": "export_job_logs", "journey_id": "JRN-123", "job_id": "JOB-456", "output_file": "logs.json", "export_format": "json"}
        """
        try:
            # Create request object with validation
            request = LogsAndReportsActionRequest(
                action=action,
                journey_id=journey_id,
                job_id=job_id,
                stage_name=stage_name,
                step_name=step_name,
                log_level=log_level,
                log_message=log_message,
                search_query=search_query,
                log_source=log_source,
                log_details=log_details,
                report_type=report_type,
                report_title=report_title,
                report_content=report_content,
                report_summary=report_summary,
                output_file=output_file,
                export_format=export_format,
                level_filter=level_filter,
                step_filter=step_filter,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )
            
            # Execute via service
            service = LogsAndReportsService()
            response = await service.execute_action(request)
            
            # Response is already in standardized format from service (Rule 9.1)
            return response
            
        except ValueError as e:
            # Validation error
            from datetime import datetime, timezone
            return {
                "result": {
                    "status": "error",
                    "message": f"Validation error: {str(e)}",
                    "operation": action,
                    "error_code": "VALIDATION_ERROR",
                    "error_details": {"error": str(e)}
                },
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        except Exception as e:
            # Unexpected error
            from datetime import datetime, timezone
            return {
                "result": {
                    "status": "error",
                    "message": f"Unexpected error: {str(e)}",
                    "operation": action,
                    "error_code": "INTERNAL_ERROR",
                    "error_details": {"error": str(e)}
                },
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }

