"""
LocalStack Configuration Module for starhub-backend

This module provides configuration management for LocalStack integration,
enabling seamless switching between LocalStack and real AWS services.

Configuration Loading:
- ECS Platform: Environment variables from task definition
- Local Development: .env.local file from project root
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Load .env.local for Local Development
# =============================================================================

def _load_env_local():
    """Load environment variables from .env.local for local development.

    The library is import-safe: it does NOT auto-load .env files. The host
    application is responsible for loading its own environment via Makefile
    or explicit load_dotenv() before importing nexus_ai_engine.
    """
    return

_load_env_local()

_SERVICE_ENDPOINT_VARS: dict[str, tuple[str, ...]] = {
    "dynamodb": ("SCYLLA_ENDPOINT", "DYNAMODB_ENDPOINT", "AWS_ENDPOINT_URL_DYNAMODB"),
    "s3": ("MINIO_ENDPOINT", "S3_ENDPOINT", "AWS_ENDPOINT_URL_S3"),
    "glue": ("MINISTACK_ENDPOINT", "GLUE_ENDPOINT", "AWS_ENDPOINT_URL_GLUE"),
}


def _first_env(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value.strip()
    return None


def _split_endpoints_configured() -> bool:
    return any(_first_env(*keys) for keys in _SERVICE_ENDPOINT_VARS.values())


@dataclass
class LocalStackConfig:
    """
    Configuration for LocalStack integration.
    
    Attributes:
        enabled: Whether LocalStack mode is active
        host: LocalStack host (default: localhost)
        port: LocalStack port (default: 4566)
        region: AWS region to use (default: us-east-1)
        access_key: Dummy access key for LocalStack (default: test)
        secret_key: Dummy secret key for LocalStack (default: test)
    """
    enabled: bool
    host: str
    port: int
    region: str
    access_key: str
    secret_key: str
    
    @classmethod
    def from_environment(cls) -> 'LocalStackConfig':
        """
        Load LocalStack configuration from environment variables.
        
        Environment Variables:
            USE_LOCALSTACK: Set to 'true' to enable LocalStack mode
            LOCALSTACK_HOST: LocalStack host (default: localhost)
            LOCALSTACK_PORT: LocalStack port (default: 4566)
            AWS_DEFAULT_REGION: AWS region (default: us-east-1)
            AWS_ACCESS_KEY_ID: Access key (default: test in LocalStack mode)
            AWS_SECRET_ACCESS_KEY: Secret key (default: test in LocalStack mode)
        
        Returns:
            LocalStackConfig instance with settings from environment
        """
        use_localstack = os.getenv('USE_LOCALSTACK', 'false').lower().strip()
        aws_emulation = os.getenv('AWS_EMULATION', '').lower().strip()
        enabled = (
            use_localstack == 'true'
            or aws_emulation == 'local'
            or _split_endpoints_configured()
        )
        
        host = os.getenv('LOCALSTACK_HOST', 'localhost').strip()
        
        # Parse port with fallback
        port_str = os.getenv('LOCALSTACK_PORT', '4566').strip()
        try:
            port = int(port_str)
        except ValueError:
            logger.warning(f"Invalid LOCALSTACK_PORT '{port_str}', using default 4566")
            port = 4566
        
        region = os.getenv('AWS_DEFAULT_REGION') or os.getenv('AWS_REGION') or 'us-east-1'
        region = region.strip()
        
        # In LocalStack mode, use dummy credentials if not specified
        if enabled:
            access_key = os.getenv('AWS_ACCESS_KEY_ID', 'test').strip()
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'test').strip()
            # Default to 'test' if empty
            if not access_key:
                access_key = 'test'
            if not secret_key:
                secret_key = 'test'
        else:
            access_key = os.getenv('AWS_ACCESS_KEY_ID', '').strip()
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', '').strip()
        
        config = cls(
            enabled=enabled,
            host=host,
            port=port,
            region=region,
            access_key=access_key,
            secret_key=secret_key
        )
        
        if enabled:
            logger.info(f"LocalStack mode enabled - endpoint: {config.endpoint_url}")
        else:
            logger.debug("LocalStack mode disabled - using real AWS endpoints")
        
        return config
    
    @property
    def endpoint_url(self) -> str:
        """
        Get the LocalStack endpoint URL.
        
        Returns:
            Full endpoint URL (e.g., http://localhost:4566)
        """
        return f"http://{self.host}:{self.port}"
    
    def get_service_endpoint(self, service: str) -> Optional[str]:
        """
        Get endpoint URL for a specific AWS service.
        
        LocalStack uses a single gateway for all services, so this returns
        the same endpoint for all services when LocalStack is enabled.
        
        Args:
            service: AWS service name (e.g., 'dynamodb', 's3', 'cloudwatch')
        
        Returns:
            Endpoint URL if LocalStack is enabled, None otherwise
        """
        # Per-service split endpoints (K3s Scylla/MinIO/MiniStack)
        for env_key in _SERVICE_ENDPOINT_VARS.get(service, ()):
            override = _first_env(env_key)
            if override:
                return override

        if not self.enabled:
            return None

        # Check for service-specific endpoint override
        env_var = f"AWS_ENDPOINT_URL_{service.upper()}"
        override = os.getenv(env_var)
        if override:
            return override.strip()

        # Check for general endpoint override
        general_override = os.getenv('AWS_ENDPOINT_URL')
        if general_override:
            return general_override.strip()

        # Use LocalStack gateway endpoint
        return self.endpoint_url
    
    def get_boto3_config(self) -> dict:
        """
        Get boto3 client configuration for LocalStack.
        
        Returns:
            Dictionary with boto3 client configuration options
        """
        if not self.enabled:
            return {}
        
        return {
            'endpoint_url': self.endpoint_url,
            'aws_access_key_id': self.access_key,
            'aws_secret_access_key': self.secret_key,
            'region_name': self.region,
            'use_ssl': False,
            'verify': False
        }
    
    def __repr__(self) -> str:
        """String representation of the configuration."""
        if self.enabled:
            return f"LocalStackConfig(enabled=True, endpoint={self.endpoint_url}, region={self.region})"
        return "LocalStackConfig(enabled=False)"


# Global configuration instance (lazy-loaded)
_global_config: Optional[LocalStackConfig] = None


def get_localstack_config() -> LocalStackConfig:
    """
    Get the global LocalStack configuration instance.
    
    Returns:
        LocalStackConfig instance (creates one if not exists)
    """
    global _global_config
    if _global_config is None:
        _global_config = LocalStackConfig.from_environment()
    return _global_config


def reset_localstack_config() -> None:
    """
    Reset the global LocalStack configuration.
    
    Useful for testing or when environment variables change.
    """
    global _global_config
    _global_config = None


def is_localstack_enabled() -> bool:
    """
    Check if LocalStack mode is enabled.
    
    Returns:
        True if LocalStack mode is enabled, False otherwise
    """
    return get_localstack_config().enabled


def is_running_on_ecs() -> bool:
    """
    Check if the application is running on AWS ECS.
    
    Returns:
        True if running on ECS, False otherwise
    """
    return bool(
        os.getenv('ECS_CONTAINER_METADATA_URI') or 
        os.getenv('ECS_CONTAINER_METADATA_URI_V4')
    )


def is_aws_environment() -> bool:
    """
    Check if running in a real AWS environment (not LocalStack).
    
    Returns:
        True if running on ECS or with real AWS credentials
    """
    # Running on ECS
    if is_running_on_ecs():
        return True
    
    # LocalStack mode is NOT real AWS
    if is_localstack_enabled():
        return False
    
    # Check for explicit AWS credentials or profile
    if os.getenv('AWS_PROFILE') or os.getenv('AWS_ACCESS_KEY_ID'):
        return True
    
    return False


def get_runtime_environment() -> str:
    """
    Get the current runtime environment.
    
    Priority:
    1. Explicit ENVIRONMENT variable
    2. Running on ECS -> 'prod'
    3. LocalStack mode -> 'local'
    4. Default -> 'dev'
    
    Returns:
        Environment string: dev, stage, test, prod, or local
    """
    # Check explicit environment variable
    env = os.getenv('ENVIRONMENT', '').strip().lower()
    if env and env in {'dev', 'stage', 'test', 'prod', 'local'}:
        return env
    
    # Running on ECS defaults to prod
    if is_running_on_ecs():
        return 'prod'
    
    # LocalStack mode
    if is_localstack_enabled():
        return 'local'
    
    # Default to dev
    return 'dev'
