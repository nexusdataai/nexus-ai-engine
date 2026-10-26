"""
Journey Management Service

This service provides async methods for journey, stage, and rule management operations.
It wraps the DynamoDB operations and provides clean interfaces for the MCP tool.

Memory-safety: Uses bounded semaphore for concurrent job execution limits.
"""

import asyncio
import os
import sys
import weakref
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime
import traceback
from loguru import logger

# Configuration for concurrent job limits
MAX_CONCURRENT_JOBS = 10  # Maximum number of jobs running simultaneously
JOB_TASK_CLEANUP_INTERVAL = 60  # Seconds between task cleanup runs


def _convert_decimal_iterative(obj: Any) -> Any:
    """
    Convert Decimal objects to float using iterative approach.
    
    Uses a stack-based algorithm to handle deeply nested structures
    without risking stack overflow from deep recursion.
    
    Args:
        obj: Object to convert (can be dict, list, tuple, or scalar)
        
    Returns:
        Object with all Decimals converted to float
    """
    # Handle simple cases directly
    if isinstance(obj, Decimal):
        return float(obj)
    if not isinstance(obj, (dict, list, tuple)):
        return obj
    
    # Use a stack to track work items: (container, key/index, value_to_process)
    # We build the result incrementally
    
    # First pass: create shallow copies and collect items to process
    if isinstance(obj, dict):
        result = {}
        stack = [(result, k, v) for k, v in obj.items()]
    elif isinstance(obj, tuple):
        # For tuples, we first process as list then convert
        temp_list: List[Any] = [None] * len(obj)
        stack = [(temp_list, i, v) for i, v in enumerate(obj)]
        # Mark that we need to convert to tuple at the end
        is_tuple = True
        result = temp_list
    else:  # list
        result = [None] * len(obj)
        stack = [(result, i, v) for i, v in enumerate(obj)]
        is_tuple = False
    
    # Track containers we've already processed to avoid infinite loops
    seen_ids: Set[int] = {id(obj)}
    
    while stack:
        container, key, value = stack.pop()
        
        if isinstance(value, Decimal):
            container[key] = float(value)
        elif isinstance(value, dict):
            obj_id = id(value)
            if obj_id in seen_ids:
                # Circular reference - just copy as-is
                container[key] = value
            else:
                seen_ids.add(obj_id)
                new_dict: Dict[str, Any] = {}
                container[key] = new_dict
                # Add items to process
                for k, v in value.items():
                    stack.append((new_dict, k, v))
        elif isinstance(value, list):
            obj_id = id(value)
            if obj_id in seen_ids:
                container[key] = value
            else:
                seen_ids.add(obj_id)
                new_list: List[Any] = [None] * len(value)
                container[key] = new_list
                for i, v in enumerate(value):
                    stack.append((new_list, i, v))
        elif isinstance(value, tuple):
            obj_id = id(value)
            if obj_id in seen_ids:
                container[key] = value
            else:
                seen_ids.add(obj_id)
                # Process tuple as list first
                temp: List[Any] = [None] * len(value)
                for i, v in enumerate(value):
                    stack.append((temp, i, v))
                # We need to convert this to tuple after processing
                # Store a marker in the container
                container[key] = ('__tuple_marker__', temp)
        else:
            container[key] = value
    
    # Second pass: convert tuple markers back to tuples
    def _finalize_tuples(container: Any) -> Any:
        if isinstance(container, dict):
            for k, v in list(container.items()):
                if isinstance(v, tuple) and len(v) == 2 and v[0] == '__tuple_marker__':
                    container[k] = tuple(_finalize_tuples(item) for item in v[1])
                elif isinstance(v, (dict, list)):
                    _finalize_tuples(v)
        elif isinstance(container, list):
            for i, v in enumerate(container):
                if isinstance(v, tuple) and len(v) == 2 and v[0] == '__tuple_marker__':
                    container[i] = tuple(_finalize_tuples(item) for item in v[1])
                elif isinstance(v, (dict, list)):
                    _finalize_tuples(v)
        return container
    
    result = _finalize_tuples(result)
    
    # Convert root to tuple if original was tuple
    if isinstance(obj, tuple):
        return tuple(result)
    
    return result

from ..adapters.dynamodb import ComprehensiveJourneyManager

from ..models.journey_model import (
    JourneyActionRequest,
    JourneyResponse,
    JourneyListResponse,
    JourneySummary,
    JobMetrics,
    convert_to_journey_data,
    convert_to_stage_data,
    convert_to_rule_data,
)

# Import job executor for running transformation jobs
from ..execution.transformation_job_executor import TransformationJobExecutor


class JourneyService:
    """
    Service class for journey management operations.
    
    Provides async interface to journey, stage, and rule management.
    Handles DynamoDB operations and Decimal serialization.
    
    Memory-safety: Uses semaphore to limit concurrent job executions and
    tracks background tasks for proper cleanup.
    """
    
    # Class-level semaphore shared across instances
    _job_semaphore: Optional[asyncio.Semaphore] = None
    _running_tasks: Set[asyncio.Task] = set()
    _job_tasks: Dict[str, asyncio.Task] = {}
    _task_cleanup_task: Optional[asyncio.Task] = None
    
    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """Get or create the job execution semaphore."""
        if cls._job_semaphore is None:
            cls._job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        return cls._job_semaphore
    
    @classmethod
    def _register_task(cls, task: asyncio.Task, job_id: str = None) -> None:
        """Register a background task for tracking."""
        cls._running_tasks.add(task)
        if job_id:
            cls._job_tasks[job_id] = task
        def _cleanup(t):
            cls._running_tasks.discard(t)
            if job_id:
                cls._job_tasks.pop(job_id, None)
        task.add_done_callback(_cleanup)

    @classmethod
    def cancel_running_job(cls, job_id: str) -> bool:
        from ..execution.transformation_job_executor import TransformationJobExecutor
        from .job_queue_service import drop_queue_job, is_queue_mode

        TransformationJobExecutor.cancel_job_execution(job_id)
        if is_queue_mode():
            drop_queue_job(job_id)
        task = cls._job_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled asyncio task for job {job_id}")
            return True
        logger.info(f"No active task found for job {job_id} on this pod (may be on another pod)")
        return False
    
    @classmethod
    def get_running_job_count(cls) -> int:
        """Get the number of currently running background jobs."""
        # Clean up done tasks
        cls._running_tasks = {t for t in cls._running_tasks if not t.done()}
        return len(cls._running_tasks)
    
    @classmethod
    def get_job_stats(cls) -> Dict[str, Any]:
        """Get job execution statistics."""
        running_count = cls.get_running_job_count()
        return {
            "running_jobs": running_count,
            "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
            "semaphore_available": MAX_CONCURRENT_JOBS - running_count,
        }
    
    def __init__(self):
        """Initialize the journey service"""
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
        Convert Decimal objects to float for JSON serialization.
        
        Uses an iterative approach with a stack to avoid recursion depth issues
        with deeply nested structures.
        
        Args:
            obj: Object to convert
            
        Returns:
            Object with Decimals converted to float
        """
        return _convert_decimal_iterative(obj)
    
    async def execute_action(self, request: JourneyActionRequest) -> JourneyResponse:
        """
        Execute a journey management action.
        
        Args:
            request: JourneyActionRequest with action and parameters
            
        Returns:
            JourneyResponse with operation result
        """
        try:
            action = request.action
            
            # Route to appropriate handler based on action
            if action == "create":
                return await self.create_journey(request)
            elif action == "read":
                return await self.get_journey(request)
            elif action == "update":
                return await self.update_journey(request)
            elif action == "delete":
                return await self.delete_journey(request)
            elif action == "list":
                return await self.list_journeys(request)
            elif action == "list_stages":
                return await self.list_stages(request)
            elif action == "add_stage":
                return await self.add_stage(request)
            elif action == "update_stage":
                return await self.update_stage(request)
            elif action == "delete_stage":
                return await self.delete_stage(request)
            elif action == "add_default_stages":
                return await self.add_default_stages(request)
            elif action == "list_rules":
                return await self.list_rules(request)
            elif action == "add_rule":
                return await self.add_rule(request)
            elif action == "update_rule":
                return await self.update_rule(request)
            elif action == "delete_rule":
                return await self.delete_rule(request)
            elif action == "export_complete":
                return await self.export_journey(request)
            elif action == "import_complete":
                return await self.import_journey(request)
            elif action == "dashboard":
                return await self.get_dashboard(request)
            elif action == "get_journey_summary":
                return await self.get_journey_summary(request)
            elif action == "get_comprehensive":
                return await self.get_comprehensive(request)
            elif action == "update_job_status":
                return await self.update_job_status(request)
            elif action == "get_job_metrics":
                return await self.get_job_metrics(request)
            elif action == "get_job_timeline":
                return await self.get_job_timeline(request)
            elif action == "batch_cancel_jobs":
                return await self.batch_cancel_jobs(request)
            elif action == "run_job":
                return await self.run_job(request)
            elif action == "clean_all":
                return await self.clean_all_journeys(request)
            elif action == "get_aggregate_report":
                return await self.get_aggregate_report(request)
            else:
                return JourneyResponse(
                    status="error",
                    message=f"Unknown action: {action}",
                    operation=action,
                    error=f"Action '{action}' is not supported"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error executing action: {str(e)}",
                operation=request.action,
                error=str(e)
            )
    
    # =============================================================================
    # JOURNEY OPERATIONS
    # =============================================================================
    
    async def create_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Create a new journey with provided stages (no default stages)"""
        try:
            # Extract stages from journey_data
            stages = None
            if request.journey_data:
                if isinstance(request.journey_data, dict):
                    # Pop stages from dict to avoid passing to manager
                    stages = request.journey_data.pop('stages', None)
                    journey_data = convert_to_journey_data(request.journey_data)
                else:
                    # It's a JourneyData model
                    stages = request.journey_data.stages
                    # Convert to dict and remove stages
                    journey_data = convert_to_journey_data(request.journey_data)
                    if 'stages' in journey_data:
                        del journey_data['stages']
            else:
                journey_data = {
                    "name": request.name,
                    "odaComponentType": request.odaComponentType,
                }
                if request.description:
                    journey_data["description"] = request.description
            
            # Validate at least one stage is provided
            if not stages or len(stages) == 0:
                return JourneyResponse(
                    status="error",
                    message="At least one stage is required to create a journey. Provide stages in journey_data.stages",
                    operation="create_journey",
                    error="No stages provided"
                )
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                # Create journey WITHOUT default stages
                journey_id = await loop.run_in_executor(
                    None,
                    lambda: self.manager.create_journey_complete(
                        journey_data,
                        include_default_stages=False,
                        include_default_rules=False
                    )
                )
            except Exception as e:
                logger.error(f"Error in create_journey_complete: {e}", exc_info=True)
                journey_id = None
            
            # Check for stored error message
            if not journey_id and hasattr(self.manager, '_last_error'):
                error_msg = getattr(self.manager, '_last_error', 'Unknown error')
                logger.error(f"Journey creation failed: {error_msg}")
            
            if journey_id:
                # Add provided stages to the journey
                stages_added = 0
                for stage in stages:
                    # Convert stage to dict if it's a model
                    if hasattr(stage, 'model_dump'):
                        stage_data = stage.model_dump(exclude_none=True)
                    elif isinstance(stage, dict):
                        stage_data = stage
                    else:
                        continue

                    stage_data = convert_to_stage_data(stage_data)
                    try:
                        success = await loop.run_in_executor(
                            None,
                            self.manager.add_stage,
                            journey_id,
                            stage_data
                        )
                        if success:
                            stages_added += 1
                            logger.info(f"Added stage '{stage_data.get('stageId', 'unknown')}' to journey {journey_id}")
                        else:
                            logger.warning(f"Failed to add stage '{stage_data.get('stageId', 'unknown')}' to journey {journey_id}")
                    except Exception as e:
                        logger.error(f"Error adding stage: {e}")
                
                # Get the created journey details
                journey = await loop.run_in_executor(
                    None,
                    self.manager.get_journey_complete,
                    journey_id
                )
                
                return JourneyResponse(
                    status="success",
                    message=f"Journey created successfully with {stages_added} stage(s)",
                    operation="create_journey",
                    journey_id=journey_id,
                    data=self._convert_decimal(journey) if journey else None
                )
            else:
                # Get detailed error if available
                error_details = "Journey creation returned None"
                if hasattr(self.manager, '_last_error') and self.manager._last_error:
                    error_details = self.manager._last_error
                
                logger.error(f"Journey creation failed: {error_details}")
                return JourneyResponse(
                    status="error",
                    message="Failed to create journey",
                    operation="create_journey",
                    error=error_details
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error creating journey: {str(e)}",
                operation="create_journey",
                error=str(e)
            )
    
    async def get_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get journey details"""
        try:
            loop = asyncio.get_event_loop()
            journey = await loop.run_in_executor(
                None,
                self.manager.get_journey_complete,
                request.journey_id
            )
            
            if journey:
                return JourneyResponse(
                    status="success",
                    message="Journey retrieved successfully",
                    operation="get_journey",
                    journey_id=request.journey_id,
                    data=self._convert_decimal(journey)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message=f"Journey not found: {request.journey_id}",
                    operation="get_journey",
                    journey_id=request.journey_id,
                    error="Journey not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error retrieving journey: {str(e)}",
                operation="get_journey",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def update_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Update journey metadata"""
        try:
            # Prepare journey data
            if request.journey_data:
                journey_data = convert_to_journey_data(request.journey_data)
            else:
                # Build journey_data from individual fields
                journey_data = {}
                if request.description is not None:
                    journey_data["description"] = request.description
                if request.name is not None:
                    journey_data["name"] = request.name
                if request.odaComponentType is not None:
                    journey_data["odaComponentType"] = request.odaComponentType
                if request.priority is not None:
                    journey_data["priority"] = request.priority
                if request.status is not None:
                    journey_data["status"] = request.status
                if request.estimatedDuration is not None:
                    journey_data["estimatedDuration"] = request.estimatedDuration
                if request.tags is not None:
                    journey_data["tags"] = request.tags
                if request.version is not None:
                    journey_data["version"] = request.version
                if request.lastModified is not None:
                    journey_data["lastModified"] = request.lastModified
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.update_journey_metadata,
                request.journey_id,
                journey_data
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Journey updated successfully",
                    operation="update_journey",
                    journey_id=request.journey_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to update journey",
                    operation="update_journey",
                    journey_id=request.journey_id,
                    error="Update operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error updating journey: {str(e)}",
                operation="update_journey",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def delete_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Delete a journey"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.delete_journey_complete,
                request.journey_id,
                request.confirm
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Journey deleted successfully",
                    operation="delete_journey",
                    journey_id=request.journey_id
                )
            else:
                # Get the last error from manager if available
                error_msg = getattr(self.manager, '_last_error', None) or "Delete operation failed - journey may not exist"
                return JourneyResponse(
                    status="error",
                    message="Failed to delete journey",
                    operation="delete_journey",
                    journey_id=request.journey_id,
                    error=error_msg
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error deleting journey: {str(e)}",
                operation="delete_journey",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def clean_all_journeys(self, request: JourneyActionRequest) -> JourneyResponse:
        """Delete all journeys from the system"""
        try:
            if not request.confirm:
                return JourneyResponse(
                    status="error",
                    message="Confirmation required to delete all journeys",
                    operation="clean_all",
                    error="Set confirm=true to proceed with deletion"
                )
            
            # Get all journeys first
            loop = asyncio.get_event_loop()
            journeys = await loop.run_in_executor(
                None,
                self.manager.list_journeys,
                None,
                None
            )
            
            if not journeys:
                return JourneyResponse(
                    status="success",
                    message="No journeys to delete",
                    operation="clean_all",
                    metadata={"cleaned_journeys": 0, "total_items_deleted": 0}
                )
            
            # Delete each journey
            deleted_count = 0
            total_items = 0
            failed = []
            
            for journey in journeys:
                journey_id = journey.get('journeyId')
                if journey_id:
                    try:
                        success = await loop.run_in_executor(
                            None,
                            self.manager.delete_journey_complete,
                            journey_id,
                            True  # confirm=True
                        )
                        if success:
                            deleted_count += 1
                        else:
                            failed.append(journey_id)
                    except Exception as e:
                        failed.append(f"{journey_id}: {str(e)}")
            
            return JourneyResponse(
                status="success",
                message=f"Cleaned {deleted_count} journeys",
                operation="clean_all",
                metadata={
                    "cleaned_journeys": deleted_count,
                    "failed_journeys": failed,
                    "total_attempted": len(journeys)
                }
            )
            
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error cleaning journeys: {str(e)}",
                operation="clean_all",
                error=str(e)
            )
    
    async def list_journeys(self, request: JourneyActionRequest) -> JourneyResponse:
        """List all journeys with optional filtering"""
        try:
            loop = asyncio.get_event_loop()
            journeys = await loop.run_in_executor(
                None,
                self.manager.list_journeys,
                request.status_filter,
                request.component_type_filter
            )
            
            return JourneyResponse(
                status="success",
                message=f"Found {len(journeys)} journeys",
                operation="list_journeys",
                data=self._convert_decimal(journeys),
                metadata={
                    "total_count": len(journeys),
                    "filters": {
                        "status": request.status_filter,
                        "component_type": request.component_type_filter
                    }
                }
            )
            
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error listing journeys: {str(e)}",
                operation="list_journeys",
                error=str(e)
            )
    
    # =============================================================================
    # STAGE OPERATIONS
    # =============================================================================
    
    async def list_stages(self, request: JourneyActionRequest) -> JourneyResponse:
        """List stages for a journey"""
        try:
            loop = asyncio.get_event_loop()
            stages = await loop.run_in_executor(
                None,
                self.manager.list_stages,
                request.journey_id
            )
            
            return JourneyResponse(
                status="success",
                message=f"Found {len(stages)} stages",
                operation="list_stages",
                journey_id=request.journey_id,
                data=self._convert_decimal(stages),
                metadata={"total_count": len(stages)}
            )
            
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error listing stages: {str(e)}",
                operation="list_stages",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def add_stage(self, request: JourneyActionRequest) -> JourneyResponse:
        """Add a stage to a journey"""
        try:
            stage_data = convert_to_stage_data(request.stage_data)
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.add_stage,
                request.journey_id,
                stage_data
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Stage added successfully",
                    operation="add_stage",
                    journey_id=request.journey_id,
                    stage_id=stage_data.get("stageId")
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to add stage",
                    operation="add_stage",
                    journey_id=request.journey_id,
                    error="Add stage operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error adding stage: {str(e)}",
                operation="add_stage",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def update_stage(self, request: JourneyActionRequest) -> JourneyResponse:
        """Update a stage"""
        try:
            stage_data = convert_to_stage_data(request.stage_data)
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.update_stage,
                request.journey_id,
                request.stage_id,
                stage_data
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Stage updated successfully",
                    operation="update_stage",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to update stage",
                    operation="update_stage",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    error="Update stage operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error updating stage: {str(e)}",
                operation="update_stage",
                journey_id=request.journey_id,
                stage_id=request.stage_id,
                error=str(e)
            )
    
    async def delete_stage(self, request: JourneyActionRequest) -> JourneyResponse:
        """Delete a stage from a journey"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.delete_stage,
                request.journey_id,
                request.stage_id,
                request.confirm
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Stage deleted successfully",
                    operation="delete_stage",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to delete stage",
                    operation="delete_stage",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    error="Delete stage operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error deleting stage: {str(e)}",
                operation="delete_stage",
                journey_id=request.journey_id,
                stage_id=request.stage_id,
                error=str(e)
            )
    
    async def add_default_stages(self, request: JourneyActionRequest) -> JourneyResponse:
        """Add all 6 default stages to a journey"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.add_default_stages_complete,
                request.journey_id
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Default stages added successfully",
                    operation="add_default_stages",
                    journey_id=request.journey_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to add default stages",
                    operation="add_default_stages",
                    journey_id=request.journey_id,
                    error="Add default stages operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error adding default stages: {str(e)}",
                operation="add_default_stages",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    # =============================================================================
    # RULE OPERATIONS
    # =============================================================================
    
    async def list_rules(self, request: JourneyActionRequest) -> JourneyResponse:
        """List Second Brain rules for a journey"""
        try:
            loop = asyncio.get_event_loop()
            rules = await loop.run_in_executor(
                None,
                self.manager.list_rules,
                request.journey_id,
                request.stage_id,
                request.rule_type
            )
            
            return JourneyResponse(
                status="success",
                message=f"Found {len(rules)} rules",
                operation="list_rules",
                journey_id=request.journey_id,
                data=self._convert_decimal(rules),
                metadata={"total_count": len(rules)}
            )
            
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error listing rules: {str(e)}",
                operation="list_rules",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def add_rule(self, request: JourneyActionRequest) -> JourneyResponse:
        """Add a new rule to a journey/stage"""
        try:
            rule_data = convert_to_rule_data(request.rule_data)
            
            # Validate rule_data has required fields
            required_fields = ['title', 'description', 'type', 'priority', 'scope', 'context', 'content']
            for field in required_fields:
                if field not in rule_data:
                    return JourneyResponse(
                        status="error",
                        message=f"Missing required field in rule_data: {field}",
                        operation="add_rule",
                        journey_id=request.journey_id,
                        stage_id=request.stage_id,
                        error=f"Required field '{field}' is missing from rule_data"
                    )
            
            loop = asyncio.get_event_loop()
            rule_id = await loop.run_in_executor(
                None,
                self.manager.add_rule,
                request.journey_id,
                request.stage_id,
                rule_data
            )
            
            # The manager now returns rule_id on success, None on failure
            if rule_id:
                return JourneyResponse(
                    status="success",
                    message="Rule add operation submitted successfully",
                    operation="add_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    rule_id=rule_id  # Include rule_id in response
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to add rule",
                    operation="add_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    error="Add rule operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error adding rule: {str(e)}",
                operation="add_rule",
                journey_id=request.journey_id,
                stage_id=request.stage_id,
                error=str(e)
            )
    
    async def update_rule(self, request: JourneyActionRequest) -> JourneyResponse:
        """Update an existing rule"""
        try:
            rule_data = convert_to_rule_data(request.rule_data)
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.update_rule,
                request.journey_id,
                request.stage_id,
                request.rule_id,
                rule_data
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Rule updated successfully",
                    operation="update_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    rule_id=request.rule_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to update rule",
                    operation="update_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    rule_id=request.rule_id,
                    error="Update rule operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error updating rule: {str(e)}",
                operation="update_rule",
                journey_id=request.journey_id,
                stage_id=request.stage_id,
                rule_id=request.rule_id,
                error=str(e)
            )
    
    async def delete_rule(self, request: JourneyActionRequest) -> JourneyResponse:
        """Delete a rule from a journey"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.delete_rule,
                request.journey_id,
                request.stage_id,
                request.rule_id,
                request.confirm
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Rule deleted successfully",
                    operation="delete_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    rule_id=request.rule_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to delete rule",
                    operation="delete_rule",
                    journey_id=request.journey_id,
                    stage_id=request.stage_id,
                    rule_id=request.rule_id,
                    error="Delete rule operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error deleting rule: {str(e)}",
                operation="delete_rule",
                journey_id=request.journey_id,
                stage_id=request.stage_id,
                rule_id=request.rule_id,
                error=str(e)
            )
    
    # =============================================================================
    # UTILITY OPERATIONS
    # =============================================================================
    
    async def export_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Export complete journey data"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.export_journey_complete,
                request.journey_id,
                request.output_file
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message=f"Journey exported to {request.output_file}",
                    operation="export_complete",
                    journey_id=request.journey_id,
                    metadata={"output_file": request.output_file}
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to export journey",
                    operation="export_complete",
                    journey_id=request.journey_id,
                    error="Export operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error exporting journey: {str(e)}",
                operation="export_complete",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def import_journey(self, request: JourneyActionRequest) -> JourneyResponse:
        """Import journey from backup"""
        try:
            loop = asyncio.get_event_loop()
            journey_id = await loop.run_in_executor(
                None,
                self.manager.import_journey_complete,
                request.input_file,
                request.new_journey_id
            )
            
            if journey_id:
                return JourneyResponse(
                    status="success",
                    message=f"Journey imported successfully",
                    operation="import_complete",
                    journey_id=journey_id,
                    metadata={"input_file": request.input_file}
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to import journey",
                    operation="import_complete",
                    error="Import operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error importing journey: {str(e)}",
                operation="import_complete",
                error=str(e)
            )
    
    async def get_dashboard(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get dashboard view of journey"""
        try:
            # Get complete journey data
            loop = asyncio.get_event_loop()
            journey = await loop.run_in_executor(
                None,
                self.manager.get_journey_complete,
                request.journey_id
            )
            
            if journey:
                return JourneyResponse(
                    status="success",
                    message="Dashboard data retrieved",
                    operation="dashboard",
                    journey_id=request.journey_id,
                    data=self._convert_decimal(journey)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Journey not found",
                    operation="dashboard",
                    journey_id=request.journey_id,
                    error="Journey not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error getting dashboard: {str(e)}",
                operation="dashboard",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def get_journey_summary(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get journey summary"""
        try:
            loop = asyncio.get_event_loop()
            journey = await loop.run_in_executor(
                None,
                self.manager.get_journey_complete,
                request.journey_id
            )
            
            if journey:
                summary = journey.get("summary", {})
                return JourneyResponse(
                    status="success",
                    message="Journey summary retrieved",
                    operation="get_journey_summary",
                    journey_id=request.journey_id,
                    data=self._convert_decimal(summary)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Journey not found",
                    operation="get_journey_summary",
                    journey_id=request.journey_id,
                    error="Journey not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error getting journey summary: {str(e)}",
                operation="get_journey_summary",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def get_comprehensive(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get comprehensive journey data"""
        try:
            loop = asyncio.get_event_loop()
            journey = await loop.run_in_executor(
                None,
                self.manager.get_journey_complete,
                request.journey_id
            )
            
            if journey:
                return JourneyResponse(
                    status="success",
                    message="Comprehensive journey data retrieved",
                    operation="get_comprehensive",
                    journey_id=request.journey_id,
                    data=self._convert_decimal(journey)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Journey not found",
                    operation="get_comprehensive",
                    journey_id=request.journey_id,
                    error="Journey not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error getting comprehensive data: {str(e)}",
                operation="get_comprehensive",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    # =============================================================================
    # JOB OPERATIONS
    # =============================================================================
    
    async def update_job_status(self, request: JourneyActionRequest) -> JourneyResponse:
        """Update job status"""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.manager.update_job_status,
                request.journey_id,
                request.job_id,
                request.job_status,
                request.progress,
                request.current_step,
                request.error_message
            )
            
            if success:
                return JourneyResponse(
                    status="success",
                    message="Job status updated successfully",
                    operation="update_job_status",
                    journey_id=request.journey_id,
                    job_id=request.job_id
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Failed to update job status",
                    operation="update_job_status",
                    journey_id=request.journey_id,
                    job_id=request.job_id,
                    error="Update job status operation failed"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error updating job status: {str(e)}",
                operation="update_job_status",
                journey_id=request.journey_id,
                job_id=request.job_id,
                error=str(e)
            )
    
    async def get_job_metrics(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get job performance metrics"""
        try:
            loop = asyncio.get_event_loop()
            metrics = await loop.run_in_executor(
                None,
                self.manager.get_job_metrics,
                request.journey_id,
                request.job_id
            )
            
            if metrics:
                return JourneyResponse(
                    status="success",
                    message="Job metrics retrieved successfully",
                    operation="get_job_metrics",
                    journey_id=request.journey_id,
                    job_id=request.job_id,
                    data=self._convert_decimal(metrics)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Job metrics not found",
                    operation="get_job_metrics",
                    journey_id=request.journey_id,
                    job_id=request.job_id,
                    error="Job metrics not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error getting job metrics: {str(e)}",
                operation="get_job_metrics",
                journey_id=request.journey_id,
                job_id=request.job_id,
                error=str(e)
            )
    
    async def get_aggregate_report(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get aggregated report across all jobs for a journey"""
        try:
            loop = asyncio.get_event_loop()
            report = await loop.run_in_executor(
                None,
                self.manager.get_aggregate_report,
                request.journey_id,
            )
            if report:
                return JourneyResponse(
                    status="success",
                    message="Aggregate report generated",
                    operation="get_aggregate_report",
                    journey_id=request.journey_id,
                    data=self._convert_decimal(report)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Journey not found or no job data",
                    operation="get_aggregate_report",
                    journey_id=request.journey_id,
                    error="No data"
                )
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error generating aggregate report: {str(e)}",
                operation="get_aggregate_report",
                journey_id=request.journey_id,
                error=str(e)
            )

    async def get_job_timeline(self, request: JourneyActionRequest) -> JourneyResponse:
        """Get job execution timeline"""
        try:
            loop = asyncio.get_event_loop()
            timeline = await loop.run_in_executor(
                None,
                self.manager.get_job_timeline,
                request.journey_id,
                request.job_id
            )
            
            if timeline:
                return JourneyResponse(
                    status="success",
                    message="Job timeline retrieved successfully",
                    operation="get_job_timeline",
                    journey_id=request.journey_id,
                    job_id=request.job_id,
                    data=self._convert_decimal(timeline)
                )
            else:
                return JourneyResponse(
                    status="error",
                    message="Job timeline not found",
                    operation="get_job_timeline",
                    journey_id=request.journey_id,
                    job_id=request.job_id,
                    error="Job timeline not found"
                )
                
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error getting job timeline: {str(e)}",
                operation="get_job_timeline",
                journey_id=request.journey_id,
                job_id=request.job_id,
                error=str(e)
            )
    
    async def batch_cancel_jobs(self, request: JourneyActionRequest) -> JourneyResponse:
        """Cancel multiple jobs"""
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self.manager.batch_cancel_jobs,
                request.journey_id,
                request.job_ids,
                request.reason
            )
            
            return JourneyResponse(
                status="success",
                message=f"Batch cancel completed for {len(request.job_ids)} jobs",
                operation="batch_cancel_jobs",
                journey_id=request.journey_id,
                data=results
            )
            
        except Exception as e:
            return JourneyResponse(
                status="error",
                message=f"Error batch canceling jobs: {str(e)}",
                operation="batch_cancel_jobs",
                journey_id=request.journey_id,
                error=str(e)
            )
    
    async def run_job(self, request: JourneyActionRequest) -> JourneyResponse:
        """Execute a journey-level job (all stages) or a single stage job."""
        try:
            journey_id = request.journey_id
            stage_id = request.stage_id
            triggered_by = request.triggered_by or 'system'
            reason = request.reason or 'Automated execution via MCP'

            from .job_queue_service import (
                enqueue_job,
                is_queue_mode,
                redis_available,
            )

            if is_queue_mode():
                if not redis_available():
                    return JourneyResponse(
                        status="error",
                        message="JOB_EXECUTION_MODE=queue requires REDIS_URL but Redis is unavailable",
                        operation="run_job",
                        journey_id=journey_id,
                        error_code="REDIS_UNAVAILABLE",
                    )
                # Overflow waits in Redis. Workers enforce MAX_GLOBAL_JOBS via ActiveJobGuard.
            else:
                running_count = self.get_running_job_count()
                if running_count >= MAX_CONCURRENT_JOBS:
                    return JourneyResponse(
                        status="error",
                        message=f"Maximum concurrent jobs ({MAX_CONCURRENT_JOBS}) reached. Currently running: {running_count}. Try again later.",
                        operation="run_job",
                        journey_id=journey_id,
                        error_code="CAPACITY_EXCEEDED",
                        metadata=self.get_job_stats()
                    )
            
            loop = asyncio.get_event_loop()
            journey_exists = await loop.run_in_executor(
                None,
                self.manager.validate_journey_exists,
                journey_id
            )
            if not journey_exists:
                return JourneyResponse(
                    status="error",
                    message=f"Journey {journey_id} not found",
                    operation="run_job",
                    journey_id=journey_id,
                    error_code="JOURNEY_NOT_FOUND"
                )

            executor = TransformationJobExecutor()

            if stage_id:
                stages = await loop.run_in_executor(None, self.manager.list_stages, journey_id)
                stage_ids = [s.get('stageId') for s in stages] if stages else []
                from ..stages import list_available_stages
                available_stages = list_available_stages()
                if stage_id not in stage_ids and stage_id not in available_stages:
                    return JourneyResponse(
                        status="error",
                        message=f"Stage {stage_id} not found for journey {journey_id}. Available stages: {', '.join(stage_ids or available_stages)}",
                        operation="run_job",
                        journey_id=journey_id,
                        error_code="STAGE_NOT_FOUND"
                    )
                job_id = await loop.run_in_executor(
                    None,
                    executor.start_job_execution,
                    journey_id,
                    stage_id,
                    triggered_by,
                    reason,
                )
                operation_label = f"stage {stage_id}"
            else:
                job_id = await loop.run_in_executor(
                    None,
                    executor.start_journey_job_execution,
                    journey_id,
                    None,
                    triggered_by,
                    reason or 'Journey pipeline execution',
                )
                operation_label = "full journey pipeline"

            job_config = getattr(request, 'job_config', None) or {}
            stage_ids_for_queue: List[str] = []
            if not stage_id:
                job_record = await loop.run_in_executor(
                    None, executor.get_job_execution, journey_id, job_id
                )
                if job_record:
                    stage_ids_for_queue = job_record.get('stageIds') or []

            if is_queue_mode():
                enqueue_job(
                    job_id=job_id,
                    journey_id=journey_id,
                    job_kind="transformation",
                    stage_id=stage_id or "",
                    stage_ids=stage_ids_for_queue,
                    triggered_by=triggered_by,
                    reason=reason or "",
                    job_config=job_config,
                )
                return JourneyResponse(
                    status="success",
                    message=f"Job {job_id} queued for {operation_label}.",
                    operation="run_job",
                    journey_id=journey_id,
                    job_id=job_id,
                    data={
                        "job_id": job_id,
                        "stage_id": stage_id,
                        "job_type": "stage" if stage_id else "journey",
                        "triggered_by": triggered_by,
                        "status": "queued",
                        "status_url": f"/api/v1/journeys/{journey_id}/jobs/{job_id}/status",
                        "stream_url": f"/api/v1/journeys/{journey_id}/jobs/{job_id}/stream",
                    },
                    metadata=self.get_job_stats(),
                )
            
            semaphore = self._get_semaphore()
            
            async def _run_job_background():
                async with semaphore:
                    try:
                        logger.info(f"Starting job {job_id} (running: {self.get_running_job_count()}/{MAX_CONCURRENT_JOBS})")
                        await loop.run_in_executor(
                            None,
                            executor.execute_job,
                            journey_id,
                            job_id
                        )
                        logger.info(f"Completed job {job_id}")
                    except Exception as e:
                        logger.error(f"Background job execution failed for {job_id}: {e}")
            
            task = asyncio.create_task(_run_job_background())
            self._register_task(task, job_id=job_id)
            
            return JourneyResponse(
                status="success",
                message=f"Job {job_id} started for {operation_label}. Poll status endpoint for progress.",
                operation="run_job",
                journey_id=journey_id,
                job_id=job_id,
                data={
                    "job_id": job_id,
                    "stage_id": stage_id,
                    "job_type": "stage" if stage_id else "journey",
                    "triggered_by": triggered_by,
                    "status": "running",
                    "status_url": f"/api/v1/journeys/{journey_id}/jobs/{job_id}/status"
                },
                metadata=self.get_job_stats()
            )
            
        except ValueError as e:
            # Validation errors should fail fast
            return JourneyResponse(
                status="error",
                message=f"Validation error: {str(e)}",
                operation="run_job",
                journey_id=request.journey_id,
                error_code="VALIDATION_ERROR",
                error=str(e)
            )
        except Exception as e:
            # Other errors
            error_msg = str(e)
            error_code = "UNKNOWN_ERROR"
            
            # Categorize common errors
            if "not found" in error_msg.lower():
                error_code = "NOT_FOUND"
            elif "stage" in error_msg.lower() and "not implemented" in error_msg.lower():
                error_code = "STAGE_NOT_IMPLEMENTED"
            elif "timeout" in error_msg.lower():
                error_code = "TIMEOUT"
            
            return JourneyResponse(
                status="error",
                message=f"Failed to run job: {error_msg}",
                operation="run_job",
                journey_id=request.journey_id,
                error_code=error_code,
                error=error_msg
            )

    async def run_jobs_bulk(
        self,
        journey_ids: List[str],
        triggered_by: str = "ui",
    ) -> JourneyResponse:
        """Slim-create every job, persist in one Dynamo batch, then enqueue.

        Stage metadata is read from class attrs (no AWS client per stage).
        Workers claim immediately on XADD, so persist finishes before the
        Redis burst (14 queued → 3 running + 11 waiting).
        """
        from .job_queue_service import enqueue_jobs, is_queue_mode, redis_available
        from ..execution.transformation_job_executor import TransformationJobExecutor

        ids = [jid for jid in journey_ids if jid]
        if not ids:
            return JourneyResponse(
                status="error",
                message="No journey IDs provided",
                operation="run_jobs_bulk",
                error_code="VALIDATION_ERROR",
            )
        if not is_queue_mode():
            return JourneyResponse(
                status="error",
                message="bulk-run requires JOB_EXECUTION_MODE=queue so all jobs enter the wait stream together",
                operation="run_jobs_bulk",
                error_code="QUEUE_REQUIRED",
            )
        if not redis_available():
            return JourneyResponse(
                status="error",
                message="JOB_EXECUTION_MODE=queue requires REDIS_URL but Redis is unavailable",
                operation="run_jobs_bulk",
                error_code="REDIS_UNAVAILABLE",
            )

        loop = asyncio.get_event_loop()
        executor = TransformationJobExecutor()
        reason = "Bulk journey pipeline"

        async def _prepare(journey_id: str) -> Dict[str, Any]:
            try:
                job_id, item = await loop.run_in_executor(
                    None,
                    executor.prepare_journey_job_execution,
                    journey_id,
                    None,
                    triggered_by,
                    reason,
                )
                data = item.get("Data") or {}
                return {
                    "ok": True,
                    "job_id": job_id,
                    "journey_id": journey_id,
                    "job_kind": "transformation",
                    "stage_id": "",
                    "stage_ids": data.get("stageIds") or [],
                    "triggered_by": triggered_by,
                    "reason": reason,
                    "job_config": {},
                    "_item": item,
                }
            except Exception as exc:
                return {"journey_id": journey_id, "ok": False, "error": str(exc)}

        created = await asyncio.gather(*[_prepare(jid) for jid in ids])
        ready = [row for row in created if row.get("ok")]
        failed = [row for row in created if not row.get("ok")]
        items = [row.pop("_item") for row in ready]
        if items:
            await loop.run_in_executor(None, executor.persist_job_items, items)
            try:
                enqueue_jobs(ready)
            except Exception as exc:
                return JourneyResponse(
                    status="error",
                    message=f"Jobs created but enqueue failed: {exc}",
                    operation="run_jobs_bulk",
                    error_code="REDIS_UNAVAILABLE",
                    error=str(exc),
                )

        return JourneyResponse(
            status="success" if ready else "error",
            message=(
                f"Queued {len(ready)} job(s)"
                + (f", {len(failed)} failed" if failed else "")
            ),
            operation="run_jobs_bulk",
            data={
                "queued": len(ready),
                "failed": len(failed),
                "jobs": [
                    {
                        "journey_id": row["journey_id"],
                        "job_id": row.get("job_id"),
                        "ok": bool(row.get("ok")),
                        "error": row.get("error"),
                    }
                    for row in created
                ],
            },
            metadata=self.get_job_stats(),
        )

