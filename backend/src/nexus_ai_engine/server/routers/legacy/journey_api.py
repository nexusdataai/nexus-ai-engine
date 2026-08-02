"""
Journey Management REST API
Direct HTTP endpoints for low-latency journey operations
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json
import os
from loguru import logger


# ---------------------------------------------------------------------------
# Lightweight cached AWS clients for live log reads.
# Avoids creating a heavyweight ComprehensiveJourneyManager on every poll.
# ---------------------------------------------------------------------------
_live_log_table = None
_live_log_s3 = None
_live_log_bucket = None


def _init_live_log_clients():
    global _live_log_table, _live_log_s3, _live_log_bucket
    if _live_log_s3 is not None:
        return
    try:
        from ....config import get_config
        config = get_config()
        table_name = config.dynamodb_transformation_table
        _live_log_bucket = config.s3_journey_logs_bucket
    except Exception:
        table_name = os.environ.get('DYNAMODB_TABLE', 'TransformationSystem')
        _live_log_bucket = os.environ.get('S3_JOURNEY_LOGS_BUCKET', 'transformation-journey-logs')
    try:
        from ....adapters.aws import create_aws_resource, create_aws_client
        role_arn = os.environ.get('AWS_ROLE_ARN')
        dynamodb = create_aws_resource('dynamodb', role_arn=role_arn) if role_arn else create_aws_resource('dynamodb')
        _live_log_table = dynamodb.Table(table_name)
        _live_log_s3 = create_aws_client('s3', role_arn=role_arn) if role_arn else create_aws_client('s3')
        logger.info(f"Live-log clients initialized: table={table_name}, bucket={_live_log_bucket}")
    except Exception as exc:
        logger.error(f"Failed to init live-log clients: {exc}")


async def _read_live_logs_dynamo(job_id: str, step_name: str):
    """Try DynamoDB live-log buffer first (written on every _log call)."""
    _init_live_log_clients()
    if _live_log_table is None:
        return None
    try:
        response = await asyncio.to_thread(
            _live_log_table.get_item,
            Key={'PK': f'LIVELOG#{job_id}', 'SK': step_name},
            ConsistentRead=True,
        )
        item = response.get('Item')
        if item and 'logs_json' in item:
            logs = json.loads(item['logs_json'])
            if logs:
                logger.info(f"LIVELOG HIT dynamo {job_id}/{step_name}: {len(logs)} entries")
                return logs
    except Exception as exc:
        logger.warning(f"DynamoDB live-log read failed {job_id}/{step_name}: {exc}")
    return None


async def _read_live_logs_s3(journey_id: str, stage_name: str, job_id: str, step_name: str):
    """Direct S3 read with cached client - no ComprehensiveJourneyManager overhead."""
    _init_live_log_clients()
    if _live_log_s3 is None or _live_log_bucket is None:
        return None
    s3_key = f'journeys/{journey_id}/stages/{stage_name}/executions/{job_id}/logs/{step_name}.json'
    try:
        response = await asyncio.to_thread(
            _live_log_s3.get_object,
            Bucket=_live_log_bucket,
            Key=s3_key,
        )
        body = await asyncio.to_thread(response['Body'].read)
        logs = json.loads(body.decode('utf-8'))
        logger.info(f"LIVELOG HIT s3 {job_id}/{step_name}: {len(logs)} entries")
        return logs
    except _live_log_s3.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        logger.warning(f"S3 live-log read failed {s3_key}: {exc}")
    return None

# Import SSE manager for real-time updates
try:
    from ....events.sse_manager import sse_manager, JobEvent, EventType
    sse_available = True
except ImportError as e:
    logger.warning(f"Could not import SSE manager: {e}")
    sse_available = False

# Import from unified models directory
# Simplified imports for test API functionality
try:
    from ....models.api_models import (
        JourneyCreateRequest,
        JourneyResponse,
        JourneyStatusResponse,
        JourneyListRequest,
        JourneyBatchRequest,
        StatusEnum,
        ErrorResponse
    )
    from ....models.journey_model import JourneyActionRequest, JourneyActionResponse
    models_available = True
except ImportError as e:
    logger.warning(f"Could not import models: {e}")
    models_available = False
    # Define simple fallback models
    from pydantic import BaseModel, Field
    
    class JourneyCreateRequest(BaseModel):
        name: str = Field(..., description="Journey name")
        description: Optional[str] = Field(None, description="Journey description")
        odaComponentType: str = Field(..., description="ODA component type")
        
    class JourneyResponse(BaseModel):
        success: bool = Field(True, description="Success status")
        message: str = Field(..., description="Response message")
        journey_id: Optional[str] = Field(None, description="Journey ID")
        data: Optional[Dict[str, Any]] = Field(None, description="Journey data")

try:
    from ....services.journey_service import JourneyService
    service_available = True
except ImportError as e:
    logger.warning(f"Could not import JourneyService: {e}")
    service_available = False

# Create router
router = APIRouter()

# Initialize service (singleton pattern) if available
if service_available:
    try:
        journey_service = JourneyService()
    except Exception as e:
        logger.warning(f"Could not initialize JourneyService: {e}")
        journey_service = None
else:
    journey_service = None


# ==========================================
# Journey CRUD Operations (Direct)
# ==========================================

@router.post("/")
async def create_journey(request: JourneyCreateRequest) -> Dict[str, Any]:
    """
    Create a new journey (direct service call for low latency)
    
    This endpoint bypasses the MCP worker pool for immediate response.
    Use the MCP tool endpoint for complex journey creation with stages.
    """
    try:
        logger.info(f"Creating journey via direct API: {request.name}")
        
        if journey_service and hasattr(request, 'to_action_request'):
            # Use real service if available
            action_request = request.to_action_request()
            result = await journey_service.execute_action(action_request)
            return {
                "success": result.status == "success",
                "message": result.message,
                "journey_id": result.journey_id,
                "data": result.data
            }
        else:
            # Mock response for testing
            journey_id = f"JRN-TEST-{datetime.utcnow().timestamp():.0f}"
            return {
                "success": True,
                "message": f"Test journey '{request.name}' created successfully",
                "journey_id": journey_id,
                "data": {
                    "journeyId": journey_id,
                    "name": request.name,
                    "description": request.description,
                    "odaComponentType": request.odaComponentType,
                    "status": "pending",
                    "createdAt": datetime.utcnow().isoformat(),
                    "updatedAt": datetime.utcnow().isoformat()
                }
            }
        
    except ValueError as e:
        logger.error(f"Validation error creating journey: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating journey: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{journey_id}")
async def get_journey(journey_id: str) -> Dict[str, Any]:
    """
    Get complete journey details by ID
    """
    try:
        logger.info(f"📄 Getting complete journey details: {journey_id}")
        
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="read",
                journey_id=journey_id
            )
            
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail="Journey not found")
            
            return {
                "success": True,
                "data": result.data
            }
        else:
            # Mock response for testing
            if not journey_id.startswith("JRN-"):
                raise HTTPException(status_code=404, detail="Journey not found")
            
            return {
                "success": True,
                "data": {
                    "journeyId": journey_id,
                    "name": "Test Journey",
                    "description": "Mock journey for testing",
                    "status": "created",
                    "odaComponentType": "product-management",
                    "overallProgress": 0,
                    "currentStageId": "STAGE-1",
                    "createdAt": datetime.utcnow().isoformat(),
                    "updatedAt": datetime.utcnow().isoformat(),
                    "stages": []
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting journey: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{journey_id}/status")
async def get_journey_status(journey_id: str) -> Dict[str, Any]:
    """
    Get quick journey status (optimized for polling)
    
    This is a lightweight endpoint designed for frequent status checks.
    Returns minimal data for maximum performance.
    """
    try:
        if journey_service and models_available:
            # Use real service if available
            action_request = JourneyActionRequest(
                action="read",
                journey_id=journey_id
            )
            
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail="Journey not found")
                
            journey_data = result.data
            
            return {
                "success": True,
                "message": "Status retrieved",
                "journey_id": journey_id,
                "status": journey_data.get("status", "unknown"),
                "progress": journey_data.get("overallProgress", 0),
                "current_stage": journey_data.get("currentStageId"),
                "last_updated": journey_data.get("updatedAt", datetime.utcnow().isoformat())
            }
        else:
            # Mock response for testing
            if not journey_id.startswith("JRN-"):
                raise HTTPException(status_code=404, detail="Journey not found")
            
            return {
                "success": True,
                "message": "Status retrieved (test)",
                "journey_id": journey_id,
                "status": "running",
                "progress": 65,
                "current_stage": "STAGE-2",
                "last_updated": datetime.utcnow().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting journey status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/")
async def list_journeys(
    status: Optional[str] = Query(None),
    component_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc")
) -> Dict[str, Any]:
    """
    List journeys with filtering and pagination
    
    Direct database query for fast response times.
    """
    try:
        if journey_service and models_available:
            # Use real service if available
            action_request = JourneyActionRequest(
                action="list",
                status_filter=status if status else None,
                component_type_filter=component_type
            )
            
            result = await journey_service.execute_action(action_request)
            
            # Apply pagination and sorting (would be better done in service layer)
            journeys = result.data if isinstance(result.data, list) else []
            
            # Simple pagination
            paginated = journeys[offset:offset + limit]
            
            return {
                "success": True,
                "total": len(journeys),
                "limit": limit,
                "offset": offset,
                "data": paginated
            }
        else:
            # Mock response for testing
            test_journeys = [
                {
                    "journeyId": f"JRN-TEST-{i}",
                    "name": f"Test Journey {i}",
                    "description": f"Test description for journey {i}",
                    "status": ["pending", "running", "completed"][i % 3],
                    "odaComponentType": ["PRODUCTCATALOG", "SERVICECATALOG", "RESOURCECATALOG"][i % 3],
                    "overallProgress": i * 20,
                    "createdAt": datetime.utcnow().isoformat(),
                    "updatedAt": datetime.utcnow().isoformat()
                }
                for i in range(5)
            ]
            
            # Apply filters if provided
            if status:
                test_journeys = [j for j in test_journeys if j["status"] == status]
            if component_type:
                test_journeys = [j for j in test_journeys if j["odaComponentType"] == component_type]
            
            # Apply pagination
            paginated = test_journeys[offset:offset + limit]
            
            return {
                "success": True,
                "total": len(test_journeys),
                "limit": limit,
                "offset": offset,
                "data": paginated
            }
        
    except Exception as e:
        logger.error(f"Error listing journeys: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{journey_id}")
async def delete_journey(journey_id: str, force: bool = Query(True)) -> Dict[str, Any]:
    """
    Delete a journey
    
    API always uses force=true to skip interactive confirmation prompts.
    """
    try:
        action_request = JourneyActionRequest(
            action="delete",
            journey_id=journey_id,
            confirm=True  # Always skip confirmation in API context (no stdin)
        )
        
        result = await journey_service.execute_action(action_request)
        
        if result.status == "error":
            raise HTTPException(status_code=404, detail=result.message)
            
        return {
            "success": True,
            "message": f"Journey {journey_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting journey: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ==========================================
# Batch Operations
# ==========================================

@router.post("/batch", response_model=Dict[str, Any])
async def batch_operation(
    request: JourneyBatchRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Perform batch operations on multiple journeys
    
    For large batches, this delegates to background processing.
    """
    journey_count = len(request.journey_ids)
    
    if journey_count <= 5:
        # Small batch - process immediately
        results = []
        for journey_id in request.journey_ids:
            try:
                if request.operation == "cancel":
                    action_request = JourneyActionRequest(
                        action="update",
                        journey_id=journey_id,
                        journey_data={"status": "cancelled", "reason": request.reason}
                    )
                    result = await journey_service.execute_action(action_request)
                    results.append({"journey_id": journey_id, "status": "success"})
                # Add other operations as needed
            except Exception as e:
                results.append({"journey_id": journey_id, "status": "failed", "error": str(e)})
                
        return {
            "success": True,
            "operation": request.operation,
            "processed": len(results),
            "results": results
        }
    else:
        # Large batch - delegate to background task
        task_id = f"batch-{datetime.utcnow().timestamp()}"
        
        async def process_batch():
            logger.info(f"Processing batch operation {task_id} for {journey_count} journeys")
            # In production, this would update a task status in database
            # For now, just process in background
            for journey_id in request.journey_ids:
                try:
                    if request.operation == "cancel":
                        action_request = JourneyActionRequest(
                            action="update",
                            journey_id=journey_id,
                            journey_data={"status": "cancelled", "reason": request.reason}
                        )
                        await journey_service.execute_action(action_request)
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error in batch operation for {journey_id}: {e}")
                    
        background_tasks.add_task(process_batch)
        
        return {
            "success": True,
            "message": f"Batch operation queued for {journey_count} journeys",
            "task_id": task_id,
            "status_url": f"/api/v1/tasks/{task_id}/status"
        }


# ==========================================
# Advanced Operations
# ==========================================

@router.post("/{journey_id}/execute")
async def execute_journey(
    journey_id: str,
    async_mode: bool = Query(True)
) -> Dict[str, Any]:
    """
    Execute a journey
    
    For async_mode=true, returns immediately with execution ID.
    For async_mode=false, waits for completion (may timeout).
    """
    try:
        if async_mode:
            # Start execution and return immediately
            execution_id = f"exec-{journey_id}-{datetime.utcnow().timestamp()}"
            
            # In production, this would create an execution record
            # and delegate to a job queue or worker
            
            return {
                "success": True,
                "message": "Journey execution started",
                "journey_id": journey_id,
                "execution_id": execution_id,
                "status_url": f"/api/v1/executions/{execution_id}/status"
            }
        else:
            # Synchronous execution (with timeout)
            try:
                # This would normally trigger actual execution logic
                await asyncio.wait_for(
                    asyncio.sleep(1),  # Simulate execution
                    timeout=30.0
                )
                
                return {
                    "success": True,
                    "message": "Journey executed successfully",
                    "journey_id": journey_id,
                    "result": {"status": "completed"}
                }
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="Execution timeout")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing journey: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{journey_id}/metrics")
async def get_journey_metrics(
    journey_id: str,
    metric_type: str = Query("all", pattern="^(all|performance|errors|stages)$")
) -> Dict[str, Any]:
    """
    Get journey metrics and statistics
    
    Fast endpoint for dashboard widgets and monitoring.
    """
    try:
        # This would query metrics from a time-series database
        # or aggregated statistics table for performance
        
        metrics = {
            "journey_id": journey_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }
        
        if metric_type in ["all", "performance"]:
            metrics["metrics"]["performance"] = {
                "avg_execution_time": 145.3,
                "min_execution_time": 89.2,
                "max_execution_time": 234.7,
                "p95_execution_time": 198.5,
                "total_executions": 1247
            }
            
        if metric_type in ["all", "errors"]:
            metrics["metrics"]["errors"] = {
                "error_rate": 0.023,
                "total_errors": 29,
                "recent_errors": []
            }
            
        if metric_type in ["all", "stages"]:
            metrics["metrics"]["stages"] = {
                "total_stages": 5,
                "completed_stages": 3,
                "average_stage_time": 29.1
            }
            
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting journey metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{journey_id}/clone")
async def clone_journey(
    journey_id: str,
    new_name: str = Query(..., min_length=1, max_length=200)
) -> JourneyResponse:
    """
    Clone an existing journey
    
    Creates a new journey with the same configuration as the source.
    """
    try:
        # Get source journey
        action_request = JourneyActionRequest(
            action="read",
            journey_id=journey_id
        )
        source_result = await journey_service.execute_action(action_request)
        
        if source_result.status == "error":
            raise HTTPException(status_code=404, detail="Source journey not found")
            
        # Create clone with new name
        source_data = source_result.data
        clone_request = JourneyActionRequest(
            action="create",
            name=new_name,
            description=f"Clone of {source_data.get('name', journey_id)}",
            odaComponentType=source_data.get("odaComponentType"),
            journey_data={
                **source_data,
                "source_journey_id": journey_id,
                "cloned_at": datetime.utcnow().isoformat()
            }
        )
        
        clone_result = await journey_service.execute_action(clone_request)
        
        return JourneyResponse(
            success=True,
            message=f"Journey cloned successfully",
            journey_id=clone_result.journey_id,
            data=clone_result.data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning journey: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ==========================================
# Stage Management Endpoints
# ==========================================

@router.get("/{journey_id}/stages")
async def list_stages(journey_id: str) -> Dict[str, Any]:
    """
    List all stages for a journey
    
    Returns the stages configured for this journey with their status and configuration.
    """
    try:
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="list_stages",
                journey_id=journey_id
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            return {
                "success": True,
                "journey_id": journey_id,
                "stages": result.data if isinstance(result.data, list) else [],
                "count": len(result.data) if isinstance(result.data, list) else 0
            }
        else:
            # Mock response for testing
            return {
                "success": True,
                "journey_id": journey_id,
                "stages": [
                    {
                        "stageId": "call_process",
                        "name": "Call Processing",
                        "description": "Process Webex CC calls",
                        "status": "pending",
                        "order": 0,
                        "config": {
                            "minutes_back": 60,
                            "transcribe": True,
                            "register_glue": True,
                            "run_analysis": True
                        }
                    }
                ],
                "count": 1
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing stages: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{journey_id}/stages")
async def add_stage(
    journey_id: str,
    stage_id: str = Query(..., description="Stage ID (e.g., call_process)"),
    name: Optional[str] = Query(None, description="Stage name"),
    description: Optional[str] = Query(None, description="Stage description"),
    order: int = Query(0, description="Stage order in sequence"),
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add a stage to a journey
    
    Creates a new stage with the specified configuration.
    For call_process stage, config can include:
    - minutes_back: Time range to look back (default: 60)
    - transcribe: Enable transcription (default: True)
    - register_glue: Enable Glue registration (default: True)
    - run_analysis: Enable AI analysis (default: True)
    - s3_bucket: S3 bucket for storage
    - skip_processed: Enable deduplication (default: True)
    """
    try:
        # Build stage data
        stage_data = {
            "stageId": stage_id,
            "name": name or stage_id.replace("_", " ").title(),
            "description": description or f"Stage: {stage_id}",
            "order": order,
            "status": "pending",
            "config": config or {}
        }
        
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="add_stage",
                journey_id=journey_id,
                stage_id=stage_id,
                stage_data=stage_data
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=400, detail=result.message)
            
            return {
                "success": True,
                "message": f"Stage {stage_id} added to journey {journey_id}",
                "journey_id": journey_id,
                "stage_id": stage_id,
                "data": result.data
            }
        else:
            # Mock response for testing
            return {
                "success": True,
                "message": f"Stage {stage_id} added to journey {journey_id} (test)",
                "journey_id": journey_id,
                "stage_id": stage_id,
                "data": stage_data
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding stage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{journey_id}/stages/{stage_id}")
async def update_stage(
    journey_id: str,
    stage_id: str,
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update a stage configuration
    
    Updates the specified stage with new configuration values.
    """
    try:
        # Build update data
        stage_data = {}
        if name is not None:
            stage_data["name"] = name
        if description is not None:
            stage_data["description"] = description
        if status is not None:
            stage_data["status"] = status
        if config is not None:
            stage_data["config"] = config
            
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="update_stage",
                journey_id=journey_id,
                stage_id=stage_id,
                stage_data=stage_data
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=400, detail=result.message)
            
            return {
                "success": True,
                "message": f"Stage {stage_id} updated",
                "journey_id": journey_id,
                "stage_id": stage_id,
                "data": result.data
            }
        else:
            # Mock response for testing
            return {
                "success": True,
                "message": f"Stage {stage_id} updated (test)",
                "journey_id": journey_id,
                "stage_id": stage_id,
                "data": stage_data
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating stage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{journey_id}/stages/{stage_id}")
async def delete_stage(journey_id: str, stage_id: str) -> Dict[str, Any]:
    """
    Delete a stage from a journey
    """
    try:
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="delete_stage",
                journey_id=journey_id,
                stage_id=stage_id
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            return {
                "success": True,
                "message": f"Stage {stage_id} deleted from journey {journey_id}"
            }
        else:
            return {
                "success": True,
                "message": f"Stage {stage_id} deleted from journey {journey_id} (test)"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting stage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ==========================================
# Job Execution Endpoints
# ==========================================

@router.post("/{journey_id}/jobs")
async def run_job(
    journey_id: str,
    stage_id: str = Query(..., description="Stage ID to execute"),
    triggered_by: str = Query("api", description="Who triggered the job"),
    reason: Optional[str] = Query(None, description="Reason for execution"),
    wait_for_completion: bool = Query(False, description="Wait for job to complete"),
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run a job on a specific stage
    
    Creates and executes a job for the specified stage.
    The job runs synchronously but updates progress in DynamoDB so UI can poll.
    """
    try:
        if journey_service and models_available:
            # Execute job - the service creates the job record and runs it
            # Progress is updated in DynamoDB, so UI can poll for status
            action_request = JourneyActionRequest(
                action="run_job",
                journey_id=journey_id,
                stage_id=stage_id,
                triggered_by=triggered_by,
                reason=reason or f"API execution for stage {stage_id}"
            )
            
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=400, detail=result.message)
            
            # Return the REAL job_id created by the service
            return {
                "success": True,
                "message": result.message,
                "journey_id": journey_id,
                "job_id": result.job_id,
                "stage_id": stage_id,
                "status": result.data.get("status", "completed") if result.data else "completed",
                "status_url": f"/api/v1/journeys/{journey_id}/jobs/{result.job_id}/status",
                "data": result.data
            }
        else:
            # Mock response for testing - generate job_id and track progress
            job_id = f"JOB-{journey_id[-8:]}-{datetime.utcnow().timestamp():.0f}"
            
            # Initialize mock job progress tracker
            cache_key = f"{journey_id}:{job_id}"
            _job_progress_cache[cache_key] = {
                "step_index": 0,
                "step_progress": 0,
                "started_at": datetime.utcnow()
            }
            
            return {
                "success": True,
                "message": f"Job {job_id} started for stage {stage_id} (test)",
                "journey_id": journey_id,
                "job_id": job_id,
                "stage_id": stage_id,
                "status": "running",
                "status_url": f"/api/v1/journeys/{journey_id}/jobs/{job_id}/status",
                "data": {
                    "job_id": job_id,
                    "stage_id": stage_id,
                    "triggered_by": triggered_by,
                    "started_at": datetime.utcnow().isoformat()
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{journey_id}/jobs")
async def list_jobs(
    journey_id: str,
    stage_id: Optional[str] = Query(None, description="Filter by stage ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    List jobs for a journey
    
    Returns all jobs for the journey, optionally filtered by stage or status.
    """
    try:
        if journey_service and models_available:
            # Get journey to access jobs
            action_request = JourneyActionRequest(
                action="read",
                journey_id=journey_id,
                include_all=True
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            # Extract jobs from journey data
            journey_data = result.data or {}
            jobs = journey_data.get("jobs", [])
            
            # Apply filters
            if stage_id:
                jobs = [j for j in jobs if j.get("stageId") == stage_id]
            if status:
                jobs = [j for j in jobs if j.get("status") == status]
            
            # Apply pagination
            total = len(jobs)
            jobs = jobs[offset:offset + limit]
            
            return {
                "success": True,
                "journey_id": journey_id,
                "total": total,
                "limit": limit,
                "offset": offset,
                "jobs": jobs
            }
        else:
            # Mock response for testing
            mock_jobs = [
                {
                    "jobId": f"JOB-{i}",
                    "stageId": stage_id or "call_process",
                    "status": ["pending", "running", "completed", "failed"][i % 4],
                    "progress": i * 25,
                    "triggeredBy": "api",
                    "startedAt": datetime.utcnow().isoformat(),
                    "completedAt": datetime.utcnow().isoformat() if i % 4 == 2 else None
                }
                for i in range(4)
            ]
            
            if status:
                mock_jobs = [j for j in mock_jobs if j["status"] == status]
            
            return {
                "success": True,
                "journey_id": journey_id,
                "total": len(mock_jobs),
                "limit": limit,
                "offset": offset,
                "jobs": mock_jobs[offset:offset + limit]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{journey_id}/jobs/{job_id}")
async def get_job(journey_id: str, job_id: str) -> Dict[str, Any]:
    """
    Get detailed job information
    
    Returns comprehensive information about a specific job including
    step results, metrics, and timeline.
    """
    try:
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="get_job_metrics",
                journey_id=journey_id,
                job_id=job_id
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            return {
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "data": result.data
            }
        else:
            # Mock response for testing
            return {
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "data": {
                    "jobId": job_id,
                    "stageId": "call_process",
                    "status": "completed",
                    "progress": 100,
                    "triggeredBy": "api",
                    "startedAt": datetime.utcnow().isoformat(),
                    "completedAt": datetime.utcnow().isoformat(),
                    "duration": 125.5,
                    "steps": [
                        {"stepId": "fetch_tasks", "status": "completed", "duration": 12.3},
                        {"stepId": "deduplication", "status": "completed", "duration": 5.1},
                        {"stepId": "process_recordings", "status": "completed", "duration": 89.2},
                        {"stepId": "register_metadata", "status": "completed", "duration": 8.4},
                        {"stepId": "ai_analysis", "status": "completed", "duration": 10.5}
                    ],
                    "metrics": {
                        "tasksFound": 10,
                        "newTasks": 8,
                        "processed": 8,
                        "failed": 0,
                        "analyzed": 8
                    }
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# In-memory job progress tracking for polling (when real service not available)
_job_progress_cache: Dict[str, Dict[str, Any]] = {}

@router.get("/{journey_id}/jobs/{job_id}/status")
async def get_job_status(journey_id: str, job_id: str) -> Dict[str, Any]:
    """
    Get job status (optimized for polling)
    
    Ultra-lightweight: single DynamoDB query with ConsistentRead.
    No S3 reads, no log processing, no ComprehensiveJourneyManager.
    """
    try:
        _init_live_log_clients()
        if _live_log_table is not None:
            def _paginated_job_query():
                params = {
                    'KeyConditionExpression': 'PK = :pk AND begins_with(SK, :sk)',
                    'FilterExpression': '#data.jobId = :job_id',
                    'ExpressionAttributeNames': {'#data': 'Data'},
                    'ExpressionAttributeValues': {
                        ':pk': f'JOURNEY#{journey_id}',
                        ':sk': 'JOB#',
                        ':job_id': job_id,
                    },
                    'ConsistentRead': True,
                    'ScanIndexForward': False,
                }
                while True:
                    resp = _live_log_table.query(**params)
                    if resp.get('Items'):
                        return resp['Items']
                    if 'LastEvaluatedKey' not in resp:
                        return []
                    params['ExclusiveStartKey'] = resp['LastEvaluatedKey']

            items = await asyncio.to_thread(_paginated_job_query)
            if items:
                job_data = items[0].get('Data', {})
                current_step = (
                    job_data.get('currentStepId')
                    or job_data.get('currentStep')
                    or job_data.get('current_step')
                )
                raw_status = job_data.get('status', 'unknown')
                return {
                    "success": True,
                    "journey_id": journey_id,
                    "job_id": job_id,
                    "status": raw_status,
                    "progress": float(job_data.get('progress', 0)),
                    "current_step": current_step,
                    "current_step_index": job_data.get('currentStepIndex', 0),
                    "step_results": job_data.get('stepResults', {}),
                    "error": job_data.get('error'),
                    "last_updated": datetime.utcnow().isoformat(),
                }

        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="get_job_metrics",
                journey_id=journey_id,
                job_id=job_id
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            job_data = result.data or {}
            current_step = job_data.get("currentStepId") or job_data.get("currentStep") or job_data.get("current_step")
            
            return {
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "status": job_data.get("status", "unknown"),
                "progress": float(job_data.get("progress", 0)),
                "current_step": current_step,
                "current_step_index": job_data.get("currentStepIndex", 0),
                "step_results": job_data.get("stepResults", {}),
                "error": job_data.get("error"),
                "last_updated": datetime.utcnow().isoformat()
            }

        if True:
            # Realistic mock response - simulate step-by-step progress
            steps = ['fetch_tasks', 'deduplication', 'process_recordings', 'register_metadata', 'ai_analysis']
            cache_key = f"{journey_id}:{job_id}"
            
            # Initialize or get cached progress
            if cache_key not in _job_progress_cache:
                _job_progress_cache[cache_key] = {
                    "step_index": 0,
                    "step_progress": 0,
                    "started_at": datetime.utcnow()
                }
            
            cache = _job_progress_cache[cache_key]
            
            # Advance progress each poll (simulate ~3 seconds per step)
            cache["step_progress"] += 35  # ~3 polls per step at 2s interval
            
            if cache["step_progress"] >= 100:
                cache["step_progress"] = 0
                cache["step_index"] += 1
            
            step_index = cache["step_index"]
            step_progress = cache["step_progress"]
            
            # Calculate overall progress
            if step_index >= len(steps):
                status = "completed"
                progress = 100
                current_step = steps[-1]
                # Clean up cache
                del _job_progress_cache[cache_key]
            else:
                status = "running"
                progress = (step_index * 100 + step_progress) / len(steps)
                current_step = steps[step_index]
            
            return {
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "status": status,
                "progress": round(progress, 1),
                "current_step": current_step,
                "current_step_index": min(step_index, len(steps) - 1),
                "error": None,
                "last_updated": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{journey_id}/jobs/{job_id}/cancel")
async def cancel_job(
    journey_id: str,
    job_id: str,
    reason: Optional[str] = Query(None, description="Reason for cancellation")
) -> Dict[str, Any]:
    """
    Cancel a running job.
    Marks the job as cancelled in DynamoDB and kills the running process
    if it's executing on this pod (cooperative cancellation via in-memory flag).
    """
    try:
        process_killed = False

        if journey_service and models_available:
            from ....services.journey_service import JourneyService
            process_killed = JourneyService.cancel_running_job(job_id)

            action_request = JourneyActionRequest(
                action="update_job_status",
                journey_id=journey_id,
                job_id=job_id,
                job_status="cancelled",
                error_message=reason or "Cancelled via API"
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=400, detail=result.message)
            
            return {
                "success": True,
                "message": f"Job {job_id} cancelled",
                "journey_id": journey_id,
                "job_id": job_id,
                "process_killed": process_killed,
            }
        else:
            return {
                "success": True,
                "message": f"Job {job_id} cancelled (test)",
                "journey_id": journey_id,
                "job_id": job_id,
                "process_killed": False,
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{journey_id}/jobs/{job_id}/retry")
async def retry_job(
    journey_id: str,
    job_id: str,
    reason: Optional[str] = Query(None, description="Reason for retry")
) -> Dict[str, Any]:
    """
    Retry a failed job
    
    Creates a new job execution based on the failed job's configuration.
    """
    try:
        if journey_service and models_available:
            # Get original job to extract stage_id
            action_request = JourneyActionRequest(
                action="get_job_metrics",
                journey_id=journey_id,
                job_id=job_id
            )
            result = await journey_service.execute_action(action_request)
            
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            
            job_data = result.data or {}
            stage_id = job_data.get("stageId", "call_process")
            
            # Create new job
            run_request = JourneyActionRequest(
                action="run_job",
                journey_id=journey_id,
                stage_id=stage_id,
                triggered_by="api-retry",
                reason=reason or f"Retry of job {job_id}"
            )
            run_result = await journey_service.execute_action(run_request)
            
            if run_result.status == "error":
                raise HTTPException(status_code=400, detail=run_result.message)
            
            return {
                "success": True,
                "message": f"Job {job_id} retried",
                "journey_id": journey_id,
                "original_job_id": job_id,
                "new_job_id": run_result.job_id,
                "data": run_result.data
            }
        else:
            new_job_id = f"JOB-RETRY-{datetime.utcnow().timestamp():.0f}"
            return {
                "success": True,
                "message": f"Job {job_id} retried (test)",
                "journey_id": journey_id,
                "original_job_id": job_id,
                "new_job_id": new_job_id,
                "data": {"status": "running"}
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# LOGS AND REPORTS REST API ENDPOINTS
# =============================================================================

@router.get("/{journey_id}/jobs/{job_id}/logs")
async def get_job_logs(
    journey_id: str,
    job_id: str,
    stage_name: Optional[str] = Query(None, description="Filter by stage name"),
    step_name: Optional[str] = Query(None, description="Filter by step name"),
    level: Optional[str] = Query(None, description="Filter by log level (info, warning, error)"),
    limit: int = Query(100, description="Maximum number of logs to return")
) -> Dict[str, Any]:
    """
    Get logs for a specific job.

    Layer 1: DynamoDB live-log (written on every _log() call, always current).
    Layer 2: Direct S3 read with cached client (for flushed logs).
    Layer 3: Full service layer fallback (heavyweight, last resort).
    """
    # Resolve actual stage_id from job data (don't default to call_process)
    resolved_stage = stage_name
    if not resolved_stage:
        try:
            from ....execution.transformation_job_executor import TransformationJobExecutor
            executor = TransformationJobExecutor()
            job_data = executor.get_job_execution(journey_id, job_id)
            resolved_stage = job_data.get("stageId", "call_process") if job_data else "call_process"
        except Exception:
            resolved_stage = "call_process"
    no_cache_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }

    def _make_response(logs: list, source: str):
        return JSONResponse(
            content={
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "data": {
                    "jobId": job_id,
                    "stageId": resolved_stage,
                    "stepName": step_name,
                    "totalLogs": len(logs),
                    "logs": logs,
                },
                "metadata": {"total_count": len(logs), "source": source},
            },
            headers=no_cache_headers,
        )

    if step_name:
        # Layer 1: DynamoDB live-log
        live_logs = await _read_live_logs_dynamo(job_id, step_name)
        if live_logs:
            return _make_response(live_logs, "dynamo")

        # Layer 2: Direct S3 read (cached client, no manager overhead)
        s3_logs = await _read_live_logs_s3(journey_id, resolved_stage, job_id, step_name)
        if s3_logs:
            return _make_response(s3_logs, "s3-direct")

    # Layer 3: Full service layer (for no step_name, or when layers 1+2 miss)
    try:
        from ....services.logs_and_reports_service import LogsAndReportsService
        from ....models.logs_and_reports_model import LogsAndReportsActionRequest

        service = LogsAndReportsService()
        request = LogsAndReportsActionRequest(
            action="get_job_logs",
            journey_id=journey_id,
            job_id=job_id,
            stage_name=resolved_stage,
            step_name=step_name,
            log_level=level,
            limit=limit
        )

        result = await service.get_job_logs(request)

        result_inner = result.get("result", result)
        if result_inner.get("status") == "error":
            raise HTTPException(status_code=404, detail=result_inner.get("message", "Logs not found"))

        data = result_inner.get("data", result.get("data", {}))
        metadata = result_inner.get("metadata", result.get("metadata", {}))

        return JSONResponse(
            content={
                "success": True,
                "journey_id": journey_id,
                "job_id": job_id,
                "data": data,
                "metadata": metadata,
            },
            headers=no_cache_headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job logs: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{journey_id}/aggregate-report")
async def get_aggregate_report(journey_id: str) -> Dict[str, Any]:
    """
    Get aggregated report across all jobs for a journey.
    Reads real metrics from DynamoDB and analysis files from S3.
    """
    try:
        if journey_service and models_available:
            action_request = JourneyActionRequest(
                action="get_aggregate_report",
                journey_id=journey_id,
            )
            result = await journey_service.execute_action(action_request)
            if result.status == "error":
                raise HTTPException(status_code=404, detail=result.message)
            return {"success": True, "journey_id": journey_id, "data": result.data}
        else:
            raise HTTPException(status_code=503, detail="Journey service not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating aggregate report: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{journey_id}/jobs/{job_id}/reports")
async def get_job_reports(
    journey_id: str,
    job_id: str,
    stage_name: Optional[str] = Query(None, description="Filter by stage name")
) -> Dict[str, Any]:
    """
    Get reports for a specific job
    
    Retrieves all report files from S3 for the specified job execution.
    """
    try:
        # Import logs and reports service
        from ....services.logs_and_reports_service import LogsAndReportsService
        from ....models.logs_and_reports_model import LogsAndReportsActionRequest
        
        service = LogsAndReportsService()
        request = LogsAndReportsActionRequest(
            action="get_job_reports",
            journey_id=journey_id,
            job_id=job_id,
            stage_name=stage_name
        )
        
        result = await service.get_job_reports(request)
        
        # Handle error responses
        result_inner = result.get("result", result)
        if result_inner.get("status") == "error":
            raise HTTPException(status_code=404, detail=result_inner.get("message", "Reports not found"))
        
        # Extract data from standardized response (data is nested under result.data)
        data = result_inner.get("data", result.get("data", {}))
        metadata = result_inner.get("metadata", result.get("metadata", {}))
        
        return {
            "success": True,
            "journey_id": journey_id,
            "job_id": job_id,
            "data": data,
            "metadata": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job reports: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{journey_id}/jobs/{job_id}/reports")
async def create_job_report(
    journey_id: str,
    job_id: str,
    report_type: str = Query(..., description="Type of report (summary, performance, error_analysis, custom)"),
    report_title: str = Query(..., description="Title of the report"),
    report_summary: Optional[str] = Query(None, description="Summary of the report"),
    report_content: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a custom report for a job
    
    Creates and stores a custom report for the specified job execution.
    """
    try:
        # Import logs and reports service
        from ....services.logs_and_reports_service import LogsAndReportsService
        from ....models.logs_and_reports_model import LogsAndReportsActionRequest
        
        service = LogsAndReportsService()
        request = LogsAndReportsActionRequest(
            action="create_job_report",
            journey_id=journey_id,
            job_id=job_id,
            report_type=report_type,
            report_title=report_title,
            report_summary=report_summary,
            report_content=report_content or {"created_via": "rest_api"}
        )
        
        result = await service.create_job_report(request)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Failed to create report"))
        
        return {
            "success": True,
            "journey_id": journey_id,
            "job_id": job_id,
            "report_type": report_type,
            "report_title": report_title,
            "data": result.get("data", {}),
            "message": result.get("message", "Report created successfully")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job report: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{journey_id}/jobs/{job_id}/logs/search")
async def search_job_logs(
    journey_id: str,
    job_id: str,
    query: str = Query(..., description="Search query"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(50, description="Maximum number of results")
) -> Dict[str, Any]:
    """
    Search logs for a specific job
    
    Searches log entries for the specified job with the given query.
    """
    try:
        # Import logs and reports service
        from ....services.logs_and_reports_service import LogsAndReportsService
        from ....models.logs_and_reports_model import LogsAndReportsActionRequest
        
        service = LogsAndReportsService()
        request = LogsAndReportsActionRequest(
            action="search_logs",
            journey_id=journey_id,
            job_id=job_id,
            search_query=query,
            level_filter=level,
            limit=limit
        )
        
        result = await service.search_logs(request)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Search failed"))
        
        return {
            "success": True,
            "journey_id": journey_id,
            "job_id": job_id,
            "query": query,
            "data": result.get("data", {}),
            "metadata": result.get("metadata", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching logs: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{journey_id}/jobs/{job_id}/errors")
async def get_job_error_summary(
    journey_id: str,
    job_id: str
) -> Dict[str, Any]:
    """
    Get error summary for a specific job
    
    Returns aggregated error information for the specified job.
    """
    try:
        # Import logs and reports service
        from ....services.logs_and_reports_service import LogsAndReportsService
        from ....models.logs_and_reports_model import LogsAndReportsActionRequest
        
        service = LogsAndReportsService()
        request = LogsAndReportsActionRequest(
            action="get_error_summary",
            journey_id=journey_id,
            job_id=job_id
        )
        
        result = await service.get_error_summary(request)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Error summary not found"))
        
        return {
            "success": True,
            "journey_id": journey_id,
            "job_id": job_id,
            "data": result.get("data", {}),
            "metadata": result.get("metadata", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting error summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# =============================================================================
# WEBSOCKET ENDPOINT FOR REAL-TIME JOB UPDATES
# =============================================================================

@router.websocket("/{journey_id}/jobs/{job_id}/ws")
async def job_status_websocket(
    websocket: WebSocket,
    journey_id: str,
    job_id: str
):
    """
    WebSocket endpoint for real-time job status updates.
    
    Clients connect to receive push notifications as job progresses through steps.
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected for job {job_id}")
    
    try:
        last_status = None
        last_progress = -1
        last_step = None
        
        while True:
            # Get current job status
            try:
                if journey_service and models_available:
                    action_request = JourneyActionRequest(
                        action="get_job_metrics",
                        journey_id=journey_id,
                        job_id=job_id
                    )
                    result = await journey_service.execute_action(action_request)
                    
                    if result.status == "error":
                        await websocket.send_json({
                            "success": False,
                            "status": "error",
                            "message": result.message
                        })
                        break
                    
                    job_data = result.data or {}
                    status = job_data.get("status", "unknown")
                    progress = job_data.get("progress", 0)
                    current_step = job_data.get("currentStep") or job_data.get("current_step")
                    
                else:
                    # Mock response for testing - simulate job progress
                    import random
                    if last_progress < 0:
                        last_progress = 0
                    
                    # Simulate progress
                    if last_progress < 100:
                        last_progress = min(last_progress + random.randint(5, 15), 100)
                    
                    # Determine current step based on progress
                    steps = ['fetch_tasks', 'deduplication', 'process_recordings', 'register_metadata', 'ai_analysis']
                    step_index = min(int(last_progress / 20), len(steps) - 1)
                    current_step = steps[step_index]
                    
                    status = "completed" if last_progress >= 100 else "running"
                    progress = last_progress
                
                # Only send update if something changed
                if status != last_status or progress != last_progress or current_step != last_step:
                    update = {
                        "success": True,
                        "job_id": job_id,
                        "status": status,
                        "progress": progress,
                        "current_step": current_step,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    await websocket.send_json(update)
                    logger.debug(f"📤 Sent job update: {status} {progress}% step={current_step}")
                    
                    last_status = status
                    last_progress = progress
                    last_step = current_step
                    
                    # Close connection if job is done
                    if status in ["completed", "failed", "cancelled"]:
                        logger.info(f"✅ Job {job_id} {status}, closing WebSocket")
                        break
                
            except Exception as e:
                logger.error(f"Error getting job status: {e}")
                await websocket.send_json({
                    "success": False,
                    "status": "error",
                    "message": str(e)
                })
            
            # Wait before next poll (500ms for responsive updates)
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass


# =============================================================================
# SSE ENDPOINT FOR REAL-TIME JOB UPDATES (RECOMMENDED)
# =============================================================================

@router.get("/{journey_id}/jobs/{job_id}/stream")
async def stream_job_progress(journey_id: str, job_id: str):
    """
    Server-Sent Events (SSE) endpoint for real-time job progress updates.
    
    This is the recommended method for real-time updates as it:
    - Works through most proxies and load balancers
    - Has built-in browser reconnection support
    - Is simpler than WebSocket for unidirectional updates
    
    Event types:
    - step_status: Step state changes (running, completed, failed)
    - log: Real-time log entries from step execution
    - task_progress: Individual task processing progress
    - job_complete: Job finished (completed/failed)
    
    Example usage (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/journeys/JRN-123/jobs/JOB-456/stream');
    eventSource.addEventListener('step_status', (e) => {
        const data = JSON.parse(e.data);
        console.log('Step update:', data);
    });
    ```
    """
    if not sse_available:
        raise HTTPException(
            status_code=503, 
            detail="SSE streaming not available - sse_manager not loaded"
        )
    
    logger.info(f"📡 SSE stream requested for job {job_id}")
    
    async def event_generator():
        """Generate SSE events for the job"""
        try:
            async for event in sse_manager.subscribe(job_id):
                yield event
        except asyncio.CancelledError:
            logger.debug(f"SSE stream cancelled for job {job_id}")
        except Exception as e:
            logger.error(f"SSE stream error for job {job_id}: {e}")
            # Send error event before closing
            yield f"event: error\ndata: {{'message': '{str(e)}'}}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/{journey_id}/jobs/{job_id}/stream/status")
async def get_stream_status(journey_id: str, job_id: str):
    """
    Get the current SSE stream status for a job.
    
    Returns the number of active subscribers and connection info.
    """
    if not sse_available:
        return {
            "success": False,
            "message": "SSE streaming not available"
        }
    
    return {
        "success": True,
        "job_id": job_id,
        "subscriber_count": sse_manager.get_subscriber_count(job_id),
        "active_jobs": sse_manager.get_active_jobs()
    }


# ==========================================
# Admin Utilities
# ==========================================

@router.post("/admin/reset-task-tracker")
async def reset_task_tracker(
    confirm: bool = Query(False, description="Set to true to confirm reset")
) -> Dict[str, Any]:
    """
    Reset the WXCC task tracker (deduplication table).
    
    This clears all processed task records, allowing jobs to reprocess
    tasks that were previously skipped.
    
    Use when:
    - Jobs show "already processed" for tasks you want to reprocess
    - UI shows stale job state
    - Testing/development requires fresh processing
    
    WARNING: This will cause ALL tasks to be reprocessed on the next job run.
    """
    if not confirm:
        return {
            "success": False,
            "message": "Add ?confirm=true to actually reset the tracker",
            "warning": "This will clear all processed task records"
        }
    
    try:
        import boto3
        import os
        
        # Get table name from config (SSM param dynamodb/wxcc-task-table → DYNAMODB_WXCC_TASK_TABLE)
        table_name = (
            os.getenv('WXCC_TASK_TABLE') or
            os.getenv('DYNAMODB_WXCC_TASK_TABLE') or
            'call-processing-dev-wxcc-task-tracking'
        )
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table = dynamodb.Table(table_name)
        
        # Scan and delete all items
        deleted_count = 0
        scan_kwargs = {'ProjectionExpression': 'task_id'}
        
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            if not items:
                break
            
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'task_id': item['task_id']})
                    deleted_count += 1
            
            # Check for pagination
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        logger.info(f"Reset task tracker: deleted {deleted_count} items from {table_name}")
        
        return {
            "success": True,
            "message": f"Task tracker reset successfully",
            "deleted_count": deleted_count,
            "table_name": table_name
        }
        
    except Exception as e:
        logger.error(f"Error resetting task tracker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset tracker: {str(e)}")


@router.get("/admin/task-tracker")
async def list_task_tracker(
    limit: int = Query(100, ge=1, le=500, description="Max items per page"),
    next_token: Optional[str] = Query(None, description="Opaque token for next page"),
) -> Dict[str, Any]:
    """
    List task tracker (dedup table) items with per-step status.
    Returns task_id, status, step_status (overview, recording, transcript, diarization, ai_analysis, salesforce_action), step_errors.
    """
    import os
    import base64
    import json

    try:
        import sys
        scripts_path = os.path.join(os.path.dirname(__file__), '../../scripts/call-scripts')
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        from task_tracker import TaskTracker
    except ImportError as e:
        logger.warning(f"TaskTracker not available: {e}")
        raise HTTPException(status_code=503, detail="Task tracker module not available")

    table_name = (
        os.getenv('WXCC_TASK_TABLE') or
        os.getenv('DYNAMODB_WXCC_TASK_TABLE') or
        'call-processing-dev-wxcc-task-tracking'
    )
    region = os.getenv('AWS_REGION', 'us-east-1')
    tracker = TaskTracker(table_name=table_name, region=region, verbose=False)

    last_key = None
    if next_token:
        try:
            last_key = json.loads(base64.urlsafe_b64decode(next_token.encode()).decode())
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid next_token")

    try:
        out = tracker.list_items(limit=limit, last_evaluated_key=last_key)
    except Exception as e:
        logger.error(f"List task tracker failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    response = {"items": out["items"]}
    if out.get("last_evaluated_key"):
        response["next_token"] = base64.urlsafe_b64encode(
            json.dumps(out["last_evaluated_key"], default=str).encode()
        ).decode()
    return response


@router.post("/admin/task-tracker/delete")
async def delete_task_tracker_entries(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete selected task tracker (dedup) entries by task_id.
    Removed tasks will be reprocessed on the next call processing job run.
    """
    task_ids = body.get("task_ids") or []
    if not isinstance(task_ids, list):
        raise HTTPException(status_code=400, detail="task_ids must be a list of strings")
    task_ids = [str(t).strip() for t in task_ids if t]
    if not task_ids:
        return {"success": True, "deleted_count": 0, "message": "No task_ids provided"}

    import os
    import sys
    try:
        scripts_path = os.path.join(os.path.dirname(__file__), '../../scripts/call-scripts')
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        from task_tracker import TaskTracker
    except ImportError as e:
        logger.warning(f"TaskTracker not available: {e}")
        raise HTTPException(status_code=503, detail="Task tracker module not available")

    table_name = (
        os.getenv('WXCC_TASK_TABLE') or
        os.getenv('DYNAMODB_WXCC_TASK_TABLE') or
        'call-processing-dev-wxcc-task-tracking'
    )
    region = os.getenv('AWS_REGION', 'us-east-1')
    tracker = TaskTracker(table_name=table_name, region=region, verbose=False)

    try:
        deleted_count = tracker.delete_items(task_ids)
        return {"success": True, "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Delete task tracker entries failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
