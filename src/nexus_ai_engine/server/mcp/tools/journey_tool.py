"""
Journey Management MCP Tool

FastMCP tool wrapper for journey, stage, and rule management operations.
Provides comprehensive CRUD operations accessible via MCP protocol.
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional, List, Dict, Any

from ....services.journey_service import JourneyService
from ....models.journey_model import JourneyActionRequest, JourneyAction


def register_journey_tools(mcp: FastMCP):
    """
    Register journey management tools with FastMCP server.
    
    Args:
        mcp: FastMCP server instance
    """
    
    @mcp.tool(
        name="journeys_tool",
        description="Core journey, stage, and rule management (CRUD operations). Supports journey CRUD, stage management, rule management, and job utilities."
    )
    async def journeys_tool(
        action: str,
        journey_id: Optional[str] = None,
        stage_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        job_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        odaComponentType: Optional[str] = None,
        journey_data: Optional[Dict[str, Any]] = None,
        stage_data: Optional[Dict[str, Any]] = None,
        rule_data: Optional[Dict[str, Any]] = None,
        rule_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        component_type_filter: Optional[str] = None,
        include_all: bool = False,
        confirm: bool = False,
        job_status: Optional[str] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
        job_ids: Optional[List[str]] = None,
        reason: Optional[str] = None,
        triggered_by: Optional[str] = None,
        output_file: Optional[str] = None,
        input_file: Optional[str] = None,
        new_journey_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive journey management tool for TMF ODA transformation journeys.
        
        Actions:
        - Journey CRUD: create, read, update, delete, list
        - Stage Management: list_stages, add_stage, update_stage, delete_stage, add_default_stages
        - Rule Management: list_rules, add_rule, update_rule, delete_rule
        - Utilities: export_complete, import_complete, dashboard, get_journey_summary, get_comprehensive
        - Job Operations: run_job, update_job_status, get_job_metrics, get_job_timeline, batch_cancel_jobs
        
        Args:
            action: Action to perform (required)
            journey_id: Journey ID (required for most operations)
            stage_id: Stage ID (for stage operations)
            rule_id: Rule ID (for rule operations)
            job_id: Job ID (for job operations)
            name: Journey name (for create)
            description: Journey description (for create)
            odaComponentType: ODA component type (for create)
            journey_data: Journey data dict (for create/update)
            stage_data: Stage data dict (for stage operations)
            rule_data: Rule data dict (for rule operations)
            rule_type: Filter by rule type (for list_rules)
            status_filter: Filter by status (for list)
            component_type_filter: Filter by component type (for list)
            include_all: Include all details
            confirm: Skip confirmation prompts
            job_status: Job status (for update_job_status)
            progress: Job progress percentage (for update_job_status)
            current_step: Current step (for update_job_status)
            error_message: Error message (for update_job_status)
            job_ids: List of job IDs (for batch_cancel_jobs)
            reason: Reason for operation
            triggered_by: Who triggered the job execution (for run_job)
            output_file: Output file path (for export_complete)
            input_file: Input file path (for import_complete)
            new_journey_id: New journey ID (for import_complete)
        
        Returns:
            Dict with operation results including status, message, and data
            
        Example Usage:
            # List all journeys
            {"action": "list"}
            
            # Create a journey
            {"action": "create", "name": "My Journey", "odaComponentType": "PRODUCTCATALOG"}
            
            # Get journey details
            {"action": "read", "journey_id": "JRN-123"}
            
            # Add a stage
            {"action": "add_stage", "journey_id": "JRN-123", "stage_data": {...}}
            
            # List rules
            {"action": "list_rules", "journey_id": "JRN-123"}
            
            # Run a transformation job
            {"action": "run_job", "journey_id": "JRN-123", "stage_id": "raw_analysis", "triggered_by": "user"}
        """
        try:
            # Create request object with validation
            request = JourneyActionRequest(
                action=action,
                journey_id=journey_id,
                stage_id=stage_id,
                rule_id=rule_id,
                job_id=job_id,
                name=name,
                description=description,
                odaComponentType=odaComponentType,
                journey_data=journey_data,
                stage_data=stage_data,
                rule_data=rule_data,
                rule_type=rule_type,
                status_filter=status_filter,
                component_type_filter=component_type_filter,
                include_all=include_all,
                confirm=confirm,
                job_status=job_status,
                progress=progress,
                current_step=current_step,
                error_message=error_message,
                job_ids=job_ids,
                reason=reason,
                triggered_by=triggered_by,
                output_file=output_file,
                input_file=input_file,
                new_journey_id=new_journey_id,
            )
            
            # Execute via service
            service = JourneyService()
            response = await service.execute_action(request)
            
            # Convert to dict for MCP response
            return response.model_dump(exclude_none=True)
            
        except ValueError as e:
            # Validation error
            return {
                "status": "error",
                "message": f"Validation error: {str(e)}",
                "operation": action,
                "error": str(e)
            }
        except Exception as e:
            # Unexpected error
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "operation": action,
                "error": str(e)
            }

