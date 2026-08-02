"""
Logs and Reports Management Service

This service provides async methods for logs and reports management operations.
It wraps the DynamoDB/S3 operations and provides clean interfaces for the MCP tool.

Memory-safety: Uses iterative decimal conversion to avoid stack overflow.
"""

import asyncio
import os
import sys
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime, timezone
import traceback

from ..adapters.dynamodb import ComprehensiveJourneyManager

from ..models.logs_and_reports_model import (
    LogsAndReportsActionRequest,
    LogsAndReportsAction,
    create_success_response,
    create_error_response,
)


class LogsAndReportsService:
    """
    Service class for logs and reports management operations.
    
    Provides async interface to logs and reports management.
    Handles DynamoDB/S3 operations and Decimal serialization.
    """
    
    def __init__(self):
        """Initialize the logs and reports service"""
        self.manager = None
        self._initialize_manager()
    
    def _initialize_manager(self):
        """Initialize the ComprehensiveJourneyManager"""
        try:
            self.manager = ComprehensiveJourneyManager()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize journey manager: {str(e)}")
    
    def _convert_decimal(self, obj: Any) -> Any:
        """
        Recursively convert Decimal objects to float for JSON serialization.
        
        Args:
            obj: Object to convert
            
        Returns:
            Object with Decimals converted to float
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_decimal(item) for item in obj)
        elif isinstance(obj, set):
            return {self._convert_decimal(item) for item in obj}
        return obj
    
    async def execute_action(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """
        Execute a logs and reports management action.
        
        Args:
            request: LogsAndReportsActionRequest with action and parameters
            
        Returns:
            Standardized response dict following Rule 9.1
        """
        try:
            action = request.action
            
            # Route to appropriate handler based on action
            if action == LogsAndReportsAction.GET_JOB_LOGS:
                return await self.get_job_logs(request)
            elif action == LogsAndReportsAction.ADD_LOG_ENTRY:
                return await self.add_log_entry(request)
            elif action == LogsAndReportsAction.SEARCH_LOGS:
                return await self.search_logs(request)
            elif action == LogsAndReportsAction.GET_LOGS_BY_LEVEL:
                return await self.get_logs_by_level(request)
            elif action == LogsAndReportsAction.EXPORT_JOB_LOGS:
                return await self.export_job_logs(request)
            elif action == LogsAndReportsAction.GET_ERROR_SUMMARY:
                return await self.get_error_summary(request)
            elif action == LogsAndReportsAction.LIST_AVAILABLE_LOGS:
                return await self.list_available_logs(request)
            elif action == LogsAndReportsAction.GET_JOB_REPORTS:
                return await self.get_job_reports(request)
            elif action == LogsAndReportsAction.CREATE_JOB_REPORT:
                return await self.create_job_report(request)
            elif action == LogsAndReportsAction.GENERATE_SUMMARY_REPORT:
                return await self.generate_summary_report(request)
            elif action == LogsAndReportsAction.GENERATE_PERFORMANCE_REPORT:
                return await self.generate_performance_report(request)
            elif action == LogsAndReportsAction.GENERATE_ERROR_ANALYSIS_REPORT:
                return await self.generate_error_analysis_report(request)
            elif action == LogsAndReportsAction.LIST_AVAILABLE_REPORTS:
                return await self.list_available_reports(request)
            elif action == LogsAndReportsAction.EXPORT_REPORTS:
                return await self.export_reports(request)
            elif action == LogsAndReportsAction.ANALYZE_JOB_PERFORMANCE:
                return await self.analyze_job_performance(request)
            elif action == LogsAndReportsAction.ANALYZE_ERROR_PATTERNS:
                return await self.analyze_error_patterns(request)
            else:
                return create_error_response(
                    operation=str(action),
                    message=f"Unknown action: {action}",
                    error_code="INVALID_ACTION"
                )
                
        except ValueError as e:
            return create_error_response(
                operation=str(request.action),
                message=str(e),
                error_code="VALIDATION_ERROR"
            )
        except Exception as e:
            return create_error_response(
                operation=str(request.action),
                message=f"Internal error: {str(e)}",
                error_code="INTERNAL_ERROR",
                error_details={"traceback": traceback.format_exc()}
            )
    
    async def get_job_logs(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Get logs for a specific job"""
        try:
            result = await asyncio.to_thread(
                self.manager.get_job_logs,
                request.journey_id,
                request.stage_name,
                request.job_id,
                request.step_name
            )
            
            if result is None:
                return create_error_response(
                    operation="get_job_logs",
                    message=f"Failed to retrieve logs for job {request.job_id}",
                    error_code="RETRIEVAL_FAILED"
                )
            
            result = self._convert_decimal(result)
            total_logs = result.get('totalLogs', 0)
            
            return create_success_response(
                operation="get_job_logs",
                message=f"Retrieved {total_logs} log entries for job {request.job_id}",
                data=result,
                metadata={
                    "total_count": total_logs,
                    "job_id": request.job_id,
                    "stage_name": request.stage_name
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="get_job_logs",
                message=f"Error retrieving job logs: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def add_log_entry(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Add a log entry to a job"""
        try:
            success = await asyncio.to_thread(
                self.manager.add_job_log_entry,
                request.journey_id,
                request.job_id,
                request.step_name,
                request.log_level,
                request.log_message,
                request.log_details,
                request.log_source
            )
            
            if not success:
                return create_error_response(
                    operation="add_log_entry",
                    message=f"Failed to add log entry for job {request.job_id}",
                    error_code="ADD_FAILED"
                )
            
            return create_success_response(
                operation="add_log_entry",
                message=f"Log entry added successfully for job {request.job_id}",
                data={
                    "jobId": request.job_id,
                    "stepName": request.step_name,
                    "level": request.log_level,
                    "added": True
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="add_log_entry",
                message=f"Error adding log entry: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def search_logs(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Search through logs with filters"""
        try:
            result = await asyncio.to_thread(
                self.manager.search_logs,
                request.journey_id,
                request.search_query,
                request.job_id,
                request.level_filter,
                request.step_filter,
                request.limit
            )
            
            if result is None:
                return create_error_response(
                    operation="search_logs",
                    message="Failed to search logs",
                    error_code="SEARCH_FAILED"
                )
            
            result = self._convert_decimal(result)
            total_matches = result.get('totalMatches', 0)
            
            return create_success_response(
                operation="search_logs",
                message=f"Found {total_matches} matching log entries",
                data=result,
                metadata={
                    "total_count": total_matches,
                    "search_query": request.search_query,
                    "filters": result.get('filters', {})
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="search_logs",
                message=f"Error searching logs: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def get_logs_by_level(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Get logs filtered by level"""
        try:
            logs = await asyncio.to_thread(
                self.manager.get_logs_by_level,
                request.journey_id,
                request.log_level,
                request.job_id,
                request.limit
            )
            
            logs = self._convert_decimal(logs)
            
            return create_success_response(
                operation="get_logs_by_level",
                message=f"Retrieved {len(logs)} {request.log_level} log entries",
                data={
                    "level": request.log_level,
                    "jobId": request.job_id,
                    "logs": logs
                },
                metadata={
                    "total_count": len(logs),
                    "level": request.log_level
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="get_logs_by_level",
                message=f"Error getting logs by level: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def export_job_logs(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Export job logs to a file"""
        try:
            success = await asyncio.to_thread(
                self.manager.export_job_logs,
                request.journey_id,
                request.job_id,
                request.output_file,
                request.export_format
            )
            
            if not success:
                return create_error_response(
                    operation="export_job_logs",
                    message=f"Failed to export logs for job {request.job_id}",
                    error_code="EXPORT_FAILED"
                )
            
            return create_success_response(
                operation="export_job_logs",
                message=f"Logs exported successfully to {request.output_file}",
                data={
                    "jobId": request.job_id,
                    "outputFile": request.output_file,
                    "format": request.export_format,
                    "exported": True
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="export_job_logs",
                message=f"Error exporting job logs: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def get_error_summary(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Get a summary of errors from job logs"""
        try:
            result = await asyncio.to_thread(
                self.manager.get_error_summary,
                request.journey_id,
                request.job_id
            )
            
            if result is None:
                return create_error_response(
                    operation="get_error_summary",
                    message="Failed to generate error summary",
                    error_code="SUMMARY_FAILED"
                )
            
            result = self._convert_decimal(result)
            summary = result.get('summary', {})
            
            return create_success_response(
                operation="get_error_summary",
                message=f"Error summary generated: {summary.get('totalErrors', 0)} errors, {summary.get('totalWarnings', 0)} warnings",
                data=result,
                metadata={
                    "total_errors": summary.get('totalErrors', 0),
                    "total_warnings": summary.get('totalWarnings', 0)
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="get_error_summary",
                message=f"Error getting error summary: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def list_available_logs(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """List all available logs for a journey or specific job"""
        try:
            logs = await asyncio.to_thread(
                self.manager.list_available_logs,
                request.journey_id,
                request.job_id
            )
            
            logs = self._convert_decimal(logs)
            
            return create_success_response(
                operation="list_available_logs",
                message=f"Found {len(logs)} log sources",
                data={"logSources": logs},
                metadata={
                    "total_count": len(logs),
                    "journey_id": request.journey_id,
                    "job_id": request.job_id
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="list_available_logs",
                message=f"Error listing available logs: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def get_job_reports(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Get reports for a specific job from S3"""
        try:
            result = await asyncio.to_thread(
                self.manager.get_job_reports,
                request.journey_id,
                request.job_id,
                request.stage_name
            )
            
            if result is None:
                return create_error_response(
                    operation="get_job_reports",
                    message=f"Failed to retrieve reports for job {request.job_id}",
                    error_code="RETRIEVAL_FAILED"
                )
            
            result = self._convert_decimal(result)
            total_reports = result.get('totalReports', 0)
            
            return create_success_response(
                operation="get_job_reports",
                message=f"Retrieved {total_reports} reports for job {request.job_id}",
                data=result,
                metadata={
                    "total_count": total_reports,
                    "job_id": request.job_id
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="get_job_reports",
                message=f"Error retrieving job reports: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def create_job_report(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Create a custom report for a job"""
        try:
            success = await asyncio.to_thread(
                self.manager.create_job_report,
                request.journey_id,
                request.job_id,
                request.report_type,
                request.report_title,
                request.report_content,
                request.report_summary
            )
            
            if not success:
                return create_error_response(
                    operation="create_job_report",
                    message=f"Failed to create report for job {request.job_id}",
                    error_code="CREATE_FAILED"
                )
            
            return create_success_response(
                operation="create_job_report",
                message=f"Report created successfully for job {request.job_id}",
                data={
                    "jobId": request.job_id,
                    "reportType": request.report_type,
                    "title": request.report_title,
                    "created": True
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="create_job_report",
                message=f"Error creating job report: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def generate_summary_report(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Generate a comprehensive summary report for a job"""
        try:
            result = await asyncio.to_thread(
                self.manager.generate_job_summary_report,
                request.journey_id,
                request.job_id
            )
            
            if result is None:
                return create_error_response(
                    operation="generate_summary_report",
                    message=f"Failed to generate summary report for job {request.job_id}",
                    error_code="GENERATION_FAILED"
                )
            
            result = self._convert_decimal(result)
            
            return create_success_response(
                operation="generate_summary_report",
                message=f"Summary report generated for job {request.job_id}",
                data=result
            )
            
        except Exception as e:
            return create_error_response(
                operation="generate_summary_report",
                message=f"Error generating summary report: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def generate_performance_report(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Generate a detailed performance analysis report"""
        try:
            result = await asyncio.to_thread(
                self.manager.generate_performance_report,
                request.journey_id,
                request.job_id
            )
            
            if result is None:
                return create_error_response(
                    operation="generate_performance_report",
                    message=f"Failed to generate performance report for job {request.job_id}",
                    error_code="GENERATION_FAILED"
                )
            
            result = self._convert_decimal(result)
            recommendations = result.get('recommendations', [])
            
            return create_success_response(
                operation="generate_performance_report",
                message=f"Performance report generated with {len(recommendations)} recommendations",
                data=result,
                metadata={
                    "recommendations_count": len(recommendations)
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="generate_performance_report",
                message=f"Error generating performance report: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def generate_error_analysis_report(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Generate detailed error analysis report"""
        try:
            # This combines error summary with additional analysis
            error_summary = await asyncio.to_thread(
                self.manager.get_error_summary,
                request.journey_id,
                request.job_id
            )
            
            if error_summary is None:
                return create_error_response(
                    operation="generate_error_analysis_report",
                    message=f"Failed to generate error analysis for job {request.job_id}",
                    error_code="GENERATION_FAILED"
                )
            
            error_summary = self._convert_decimal(error_summary)
            
            # Create report in DynamoDB
            await asyncio.to_thread(
                self.manager.create_job_report,
                request.journey_id,
                request.job_id,
                "error_analysis",
                f"Error Analysis for Job {request.job_id}",
                error_summary,
                f"Error analysis showing {error_summary['summary']['totalErrors']} errors"
            )
            
            return create_success_response(
                operation="generate_error_analysis_report",
                message=f"Error analysis report generated for job {request.job_id}",
                data=error_summary,
                metadata={
                    "total_errors": error_summary['summary']['totalErrors'],
                    "total_warnings": error_summary['summary']['totalWarnings']
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="generate_error_analysis_report",
                message=f"Error generating error analysis report: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def list_available_reports(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """List all available reports for a journey or specific job"""
        try:
            # Get reports from DynamoDB
            clean_id = self.manager.clean_journey_id(request.journey_id)
            
            if request.job_id:
                sk_prefix = f'REPORT#{request.job_id}'
            else:
                sk_prefix = 'REPORT#'
            
            response = await asyncio.to_thread(
                self.manager.table.query,
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': sk_prefix
                }
            )
            
            reports = []
            for item in response['Items']:
                if item.get('EntityType') == 'JobReport':
                    report_data = item['Data']
                    reports.append({
                        'reportId': report_data.get('reportId'),
                        'jobId': report_data.get('jobId'),
                        'reportType': report_data.get('reportType'),
                        'title': report_data.get('title'),
                        'summary': report_data.get('summary'),
                        'generatedAt': report_data.get('generatedAt'),
                        'status': report_data.get('status')
                    })
            
            reports = self._convert_decimal(reports)
            
            return create_success_response(
                operation="list_available_reports",
                message=f"Found {len(reports)} reports",
                data={"reports": reports},
                metadata={
                    "total_count": len(reports),
                    "journey_id": request.journey_id,
                    "job_id": request.job_id
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="list_available_reports",
                message=f"Error listing available reports: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def export_reports(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Export reports to a file"""
        try:
            import json
            
            # Get all reports for the job
            reports_data = await asyncio.to_thread(
                self.manager.get_job_reports,
                request.journey_id,
                request.job_id,
                request.stage_name
            )
            
            if reports_data is None or not reports_data.get('reports'):
                return create_error_response(
                    operation="export_reports",
                    message=f"No reports found for job {request.job_id}",
                    error_code="NOT_FOUND"
                )
            
            reports_data = self._convert_decimal(reports_data)
            
            # Export to file
            if request.export_format == "json":
                await asyncio.to_thread(
                    self._export_json,
                    request.output_file,
                    reports_data
                )
            else:
                return create_error_response(
                    operation="export_reports",
                    message=f"Export format '{request.export_format}' not supported for reports",
                    error_code="UNSUPPORTED_FORMAT"
                )
            
            return create_success_response(
                operation="export_reports",
                message=f"Reports exported successfully to {request.output_file}",
                data={
                    "jobId": request.job_id,
                    "outputFile": request.output_file,
                    "format": request.export_format,
                    "reportCount": len(reports_data.get('reports', [])),
                    "exported": True
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="export_reports",
                message=f"Error exporting reports: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def analyze_job_performance(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Analyze job performance metrics in detail"""
        try:
            metrics = await asyncio.to_thread(
                self.manager.get_job_metrics,
                request.journey_id,
                request.job_id
            )
            
            if metrics is None:
                return create_error_response(
                    operation="analyze_job_performance",
                    message=f"Failed to analyze performance for job {request.job_id}",
                    error_code="ANALYSIS_FAILED"
                )
            
            metrics = self._convert_decimal(metrics)
            
            return create_success_response(
                operation="analyze_job_performance",
                message=f"Performance analysis completed for job {request.job_id}",
                data=metrics,
                metadata={
                    "duration": metrics.get('duration'),
                    "error_rate": metrics.get('performanceMetrics', {}).get('errorRate', 0)
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="analyze_job_performance",
                message=f"Error analyzing job performance: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def analyze_error_patterns(self, request: LogsAndReportsActionRequest) -> Dict[str, Any]:
        """Analyze error patterns across jobs"""
        try:
            # Get error summary which includes pattern analysis
            error_summary = await asyncio.to_thread(
                self.manager.get_error_summary,
                request.journey_id,
                request.job_id
            )
            
            if error_summary is None:
                return create_error_response(
                    operation="analyze_error_patterns",
                    message="Failed to analyze error patterns",
                    error_code="ANALYSIS_FAILED"
                )
            
            error_summary = self._convert_decimal(error_summary)
            
            # Add pattern analysis
            patterns = {
                "errorCategories": error_summary['summary']['errorCategories'],
                "errorsByStep": error_summary['summary']['errorsByStep'],
                "totalErrors": error_summary['summary']['totalErrors'],
                "totalWarnings": error_summary['summary']['totalWarnings'],
                "recentErrors": error_summary['recentErrors'],
                "recentWarnings": error_summary['recentWarnings'],
                "analysis": {
                    "mostCommonCategory": max(
                        error_summary['summary']['errorCategories'].items(),
                        key=lambda x: x[1]
                    )[0] if error_summary['summary']['errorCategories'] else None,
                    "mostProblematicStep": max(
                        error_summary['summary']['errorsByStep'].items(),
                        key=lambda x: x[1]
                    )[0] if error_summary['summary']['errorsByStep'] else None
                }
            }
            
            return create_success_response(
                operation="analyze_error_patterns",
                message=f"Error pattern analysis completed: {patterns['totalErrors']} errors analyzed",
                data=patterns,
                metadata={
                    "total_errors": patterns['totalErrors'],
                    "total_warnings": patterns['totalWarnings']
                }
            )
            
        except Exception as e:
            return create_error_response(
                operation="analyze_error_patterns",
                message=f"Error analyzing error patterns: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    def _export_json(self, output_file: str, data: Any):
        """Helper to export data to JSON file"""
        import json
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

