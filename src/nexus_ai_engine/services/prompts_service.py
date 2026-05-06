"""
Prompts Service

Service layer for managing configurable AI prompts.
Supports DynamoDB storage with fallback to default configuration.
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger

import boto3
from botocore.exceptions import ClientError

from ..models.prompt_model import (
    PromptConfig,
    PromptEntry,
    PromptAuditEntry,
    PromptMetadata,
    PromptType,
    DEFAULT_PROMPTS,
    get_default_prompts,
    get_default_prompt
)


class PromptsService:
    """Service for managing configurable AI prompts"""
    
    def __init__(self):
        """Initialize Prompts service"""
        self.capability = os.getenv('CAPABILITY_NAME', 'call-processing')
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        # DynamoDB table name follows pattern: {capability}-{env}-prompts
        self.table_name = f"{self.capability}-{self.environment}-prompts"
        
        # Config key in DynamoDB
        self.config_key = "prompts_config"
        
        # Cached config
        self._config_cache: Optional[PromptConfig] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute
        
        # Initialize DynamoDB client
        try:
            self._dynamodb = boto3.resource('dynamodb', region_name=self.region)
            self._table = self._dynamodb.Table(self.table_name)
            self._dynamodb_available = True
            logger.info(f"Prompts Service initialized with DynamoDB table: {self.table_name}")
        except Exception as e:
            logger.warning(f"DynamoDB not available for Prompts: {e}. Using default config.")
            self._dynamodb_available = False
            self._table = None
    
    def _is_cache_valid(self) -> bool:
        """Check if cached config is still valid"""
        if not self._config_cache or not self._cache_timestamp:
            return False
        
        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _invalidate_cache(self):
        """Invalidate the config cache"""
        self._config_cache = None
        self._cache_timestamp = None
    
    async def get_config(self, force_refresh: bool = False) -> PromptConfig:
        """
        Get prompts configuration.
        
        Tries to load from DynamoDB, falls back to default config.
        Uses caching to reduce DynamoDB reads.
        
        Args:
            force_refresh: If True, bypass cache and reload from source
            
        Returns:
            PromptConfig object
        """
        # Return cached config if valid
        if not force_refresh and self._is_cache_valid():
            return self._config_cache
        
        # Try loading from DynamoDB
        if self._dynamodb_available:
            try:
                response = self._table.get_item(Key={'id': self.config_key})
                
                if 'Item' in response:
                    config_data = response['Item'].get('config', {})
                    self._config_cache = PromptConfig(**config_data)
                    self._cache_timestamp = datetime.now(timezone.utc)
                    logger.debug("Loaded prompts config from DynamoDB")
                    return self._config_cache
                else:
                    # No config in DynamoDB, initialize with defaults
                    logger.info("No prompts config in DynamoDB, initializing with defaults")
                    default_config = self._get_default_config()
                    await self._save_config_to_dynamodb(default_config)
                    return await self.get_config()
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger.warning(f"Prompts DynamoDB table not found: {self.table_name}")
                else:
                    logger.error(f"DynamoDB error loading prompts config: {e}")
            except Exception as e:
                logger.error(f"Error loading prompts config: {e}")
        
        # Fallback to default config
        logger.debug("Using default prompts configuration")
        self._config_cache = self._get_default_config()
        self._cache_timestamp = datetime.now(timezone.utc)
        return self._config_cache
    
    def _get_default_config(self) -> PromptConfig:
        """Get default prompt configuration"""
        return PromptConfig(
            metadata=PromptMetadata(
                version="1.0.0",
                last_updated=datetime.now(timezone.utc),
                environment=self.environment
            ),
            prompts=get_default_prompts(),
            audit_log=[]
        )
    
    async def _save_config_to_dynamodb(self, config: PromptConfig) -> bool:
        """Save config to DynamoDB"""
        if not self._dynamodb_available:
            logger.warning("DynamoDB not available, cannot save prompts config")
            return False
        
        try:
            # Convert to dict and handle datetime serialization
            config_dict = json.loads(config.model_dump_json())
            
            self._table.put_item(
                Item={
                    'id': self.config_key,
                    'config': config_dict,
                    'updatedAt': datetime.now(timezone.utc).isoformat()
                }
            )
            
            self._invalidate_cache()
            logger.info("Saved prompts config to DynamoDB")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prompts config to DynamoDB: {e}")
            return False
    
    async def get_prompts(self) -> List[PromptEntry]:
        """Get all prompts"""
        config = await self.get_config()
        return config.prompts
    
    async def get_prompt(self, prompt_id: str) -> Optional[PromptEntry]:
        """Get a specific prompt by ID"""
        config = await self.get_config()
        for prompt in config.prompts:
            if prompt.id == prompt_id:
                return prompt
        return None
    
    async def get_prompt_content(self, prompt_id: str) -> str:
        """
        Get the content of a specific prompt (async version).
        Falls back to default if not found.
        
        This is the main method used by the AI analyzer.
        """
        prompt = await self.get_prompt(prompt_id)
        if prompt:
            return prompt.content
        
        # Fallback to default
        default_prompt = get_default_prompt(prompt_id)
        if default_prompt:
            return default_prompt.content
        
        raise ValueError(f"Unknown prompt ID: {prompt_id}")
    
    def get_prompt_content_sync(self, prompt_id: str) -> str:
        """
        Get the content of a specific prompt (synchronous version).
        
        Uses asyncio.run() to execute the async method, or falls back
        to default prompts if already in an async context.
        
        This is useful for calling from synchronous code like the call processor.
        """
        import asyncio
        
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # We're in an async context, just return default
            default_prompt = get_default_prompt(prompt_id)
            if default_prompt:
                return default_prompt.content
            raise ValueError(f"Unknown prompt ID: {prompt_id}")
        except RuntimeError:
            # No event loop, we can use asyncio.run()
            try:
                return asyncio.run(self.get_prompt_content(prompt_id))
            except Exception:
                # Fallback to default prompts on any error
                default_prompt = get_default_prompt(prompt_id)
                if default_prompt:
                    return default_prompt.content
                raise ValueError(f"Unknown prompt ID: {prompt_id}")
    
    async def update_prompt(
        self,
        prompt_id: str,
        content: str,
        user_id: str = "system"
    ) -> PromptEntry:
        """
        Update a prompt's content.
        
        Args:
            prompt_id: The prompt to update
            content: New prompt content
            user_id: User making the change (for audit)
            
        Returns:
            Updated PromptEntry
            
        Raises:
            ValueError: If prompt_id is invalid
        """
        # Validate prompt_id
        valid_ids = [pt.value for pt in PromptType]
        if prompt_id not in valid_ids:
            raise ValueError(f"Invalid prompt ID: {prompt_id}. Must be one of: {valid_ids}")
        
        # Validate content length
        max_length = DEFAULT_PROMPTS.get(prompt_id, {}).get('max_length', 10000)
        if len(content) > max_length:
            raise ValueError(f"Content exceeds maximum length of {max_length} characters")
        
        if len(content) < 10:
            raise ValueError("Content must be at least 10 characters")
        
        config = await self.get_config()
        
        # Find and update the prompt
        updated_prompt = None
        for i, prompt in enumerate(config.prompts):
            if prompt.id == prompt_id:
                # Create audit entry
                audit_entry = PromptAuditEntry(
                    timestamp=datetime.now(timezone.utc),
                    action="UPDATE",
                    user_id=user_id,
                    prompt_id=prompt_id,
                    previous_content=prompt.content[:500] if prompt.content else None,
                    new_content=content[:500]
                )
                config.audit_log.append(audit_entry)
                
                # Update the prompt
                config.prompts[i] = PromptEntry(
                    id=prompt.id,
                    name=prompt.name,
                    description=prompt.description,
                    content=content,
                    max_length=prompt.max_length,
                    placeholders=prompt.placeholders,
                    is_default=False,
                    updated_at=datetime.now(timezone.utc),
                    updated_by=user_id
                )
                updated_prompt = config.prompts[i]
                break
        
        if not updated_prompt:
            # Prompt not in config yet, add from defaults
            default = get_default_prompt(prompt_id)
            if default:
                updated_prompt = PromptEntry(
                    id=default.id,
                    name=default.name,
                    description=default.description,
                    content=content,
                    max_length=default.max_length,
                    placeholders=default.placeholders,
                    is_default=False,
                    updated_at=datetime.now(timezone.utc),
                    updated_by=user_id
                )
                config.prompts.append(updated_prompt)
                
                # Add audit entry
                audit_entry = PromptAuditEntry(
                    timestamp=datetime.now(timezone.utc),
                    action="UPDATE",
                    user_id=user_id,
                    prompt_id=prompt_id,
                    previous_content=default.content[:500],
                    new_content=content[:500]
                )
                config.audit_log.append(audit_entry)
        
        # Update metadata
        config.metadata.last_updated = datetime.now(timezone.utc)
        
        # Save to DynamoDB
        await self._save_config_to_dynamodb(config)
        
        logger.info(f"Updated prompt '{prompt_id}' by user '{user_id}'")
        return updated_prompt
    
    async def reset_to_defaults(self, user_id: str = "system") -> List[str]:
        """
        Reset all prompts to their default values.
        
        Args:
            user_id: User making the change (for audit)
            
        Returns:
            List of prompt IDs that were reset
        """
        config = await self.get_config()
        reset_ids = []
        
        # Add audit entries for each reset
        for prompt in config.prompts:
            if not prompt.is_default:
                default = get_default_prompt(prompt.id)
                if default:
                    audit_entry = PromptAuditEntry(
                        timestamp=datetime.now(timezone.utc),
                        action="RESET",
                        user_id=user_id,
                        prompt_id=prompt.id,
                        previous_content=prompt.content[:500] if prompt.content else None,
                        new_content=default.content[:500]
                    )
                    config.audit_log.append(audit_entry)
                    reset_ids.append(prompt.id)
        
        # Replace all prompts with defaults
        config.prompts = get_default_prompts()
        config.metadata.last_updated = datetime.now(timezone.utc)
        
        # Save to DynamoDB
        await self._save_config_to_dynamodb(config)
        
        logger.info(f"Reset all prompts to defaults by user '{user_id}'")
        return reset_ids
    
    async def get_audit_log(self, limit: int = 50) -> List[PromptAuditEntry]:
        """Get recent audit log entries"""
        config = await self.get_config()
        # Return most recent entries first
        sorted_log = sorted(config.audit_log, key=lambda x: x.timestamp, reverse=True)
        return sorted_log[:limit]


# Singleton instance
_prompts_service: Optional[PromptsService] = None


def get_prompts_service() -> PromptsService:
    """Get or create the prompts service singleton"""
    global _prompts_service
    if _prompts_service is None:
        _prompts_service = PromptsService()
    return _prompts_service
