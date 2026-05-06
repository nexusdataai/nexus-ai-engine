"""
Prompts API

REST API endpoints for managing configurable AI prompts.
Allows administrators to customize prompts used for call summary
and product details extraction.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from ....services.prompts_service import get_prompts_service, PromptsService
from ....models.prompt_model import (
    PromptEntry,
    PromptAuditEntry,
    UpdatePromptRequest,
    UpdatePromptResponse,
    PromptListResponse,
    PromptResetResponse,
    PromptType
)

# Auth is the host application's concern — the library's reference router
# never enforces it. nexus-backend layers its session middleware in front
# of the mounted router; library-only callers get unauthenticated access.
AUTH_AVAILABLE = False


def get_session_from_cookie(*args, **kwargs):  # pragma: no cover
    return None


def require_admin(*args, **kwargs):  # pragma: no cover
    return None


def require_executive(*args, **kwargs):  # pragma: no cover
    return None


# Create router
router = APIRouter(prefix="/api/v1/prompts", tags=["Prompt Configuration"])


def _get_user_id(session: Optional[Dict[str, Any]]) -> str:
    """Extract user ID from session, default to 'anonymous'"""
    if session and isinstance(session, dict):
        return session.get('email', session.get('sub', 'anonymous'))
    return 'anonymous'


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    prompts_service: PromptsService = Depends(get_prompts_service)
):
    """
    Get all configurable prompts.
    
    Returns a list of prompts with their current content,
    whether they are using defaults, and metadata.
    """
    try:
        prompts = await prompts_service.get_prompts()
        
        return PromptListResponse(
            success=True,
            data=prompts,
            count=len(prompts)
        )
        
    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to list prompts", "message": str(e)}
        )


@router.get("/types")
async def list_prompt_types():
    """
    Get available prompt types.
    
    Returns the valid prompt type IDs that can be configured.
    """
    types_data = [
        {"id": pt.value, "name": pt.value.replace("_", " ").title(), "description": f"Configurable prompt: {pt.value}"}
        for pt in PromptType
    ]
    return {
        "success": True,
        "data": types_data,
        "count": len(types_data)
    }


@router.get("/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    prompts_service: PromptsService = Depends(get_prompts_service)
):
    """
    Get a specific prompt by ID.
    
    Args:
        prompt_id: The prompt identifier (call_summary or product_details)
    """
    try:
        prompt = await prompts_service.get_prompt(prompt_id)
        
        if not prompt:
            raise HTTPException(
                status_code=404,
                detail={"error": "Prompt not found", "prompt_id": prompt_id}
            )
        
        return {
            "success": True,
            "data": prompt
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to get prompt", "message": str(e)}
        )


@router.put("/{prompt_id}", response_model=UpdatePromptResponse)
async def update_prompt(
    prompt_id: str,
    request: UpdatePromptRequest,
    prompts_service: PromptsService = Depends(get_prompts_service),
    session: Optional[Dict[str, Any]] = Depends(get_session_from_cookie) if AUTH_AVAILABLE else None
):
    """
    Update a prompt's content.
    
    Requires Admin role.
    
    Args:
        prompt_id: The prompt identifier to update
        request: The new prompt content
    """
    try:
        user_id = _get_user_id(session)
        
        updated_prompt = await prompts_service.update_prompt(
            prompt_id=prompt_id,
            content=request.content,
            user_id=user_id
        )
        
        return UpdatePromptResponse(
            success=True,
            message=f"Prompt '{prompt_id}' updated successfully",
            prompt_id=prompt_id,
            updated_at=updated_prompt.updated_at or datetime.utcnow()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid request", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Error updating prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to update prompt", "message": str(e)}
        )


@router.post("/reset", response_model=PromptResetResponse)
async def reset_prompts(
    prompts_service: PromptsService = Depends(get_prompts_service),
    session: Optional[Dict[str, Any]] = Depends(get_session_from_cookie) if AUTH_AVAILABLE else None
):
    """
    Reset all prompts to their default values.
    
    Requires Admin role.
    This operation cannot be undone.
    """
    try:
        user_id = _get_user_id(session)
        
        reset_ids = await prompts_service.reset_to_defaults(user_id=user_id)
        
        return PromptResetResponse(
            success=True,
            message=f"Reset {len(reset_ids)} prompt(s) to defaults",
            reset_prompts=reset_ids
        )
        
    except Exception as e:
        logger.error(f"Error resetting prompts: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to reset prompts", "message": str(e)}
        )


@router.get("/audit/log")
async def get_audit_log(
    limit: int = 50,
    prompts_service: PromptsService = Depends(get_prompts_service)
):
    """
    Get prompt change audit log.
    
    Returns recent changes to prompt configurations.
    
    Args:
        limit: Maximum number of entries to return (default 50)
    """
    try:
        if limit < 1 or limit > 500:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid limit", "message": "Limit must be between 1 and 500"}
            )
        
        audit_log = await prompts_service.get_audit_log(limit=limit)
        
        return {
            "success": True,
            "data": audit_log,
            "count": len(audit_log)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit log: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to get audit log", "message": str(e)}
        )
