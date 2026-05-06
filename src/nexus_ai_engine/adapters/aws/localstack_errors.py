"""
LocalStack Error Classes for starhub-backend

This module provides custom exception classes for LocalStack-related errors,
with descriptive messages and troubleshooting guidance.
"""

from typing import Optional


class LocalStackError(Exception):
    """
    Base exception for LocalStack-related errors.
    
    All LocalStack-specific exceptions should inherit from this class
    to enable easy catching of LocalStack issues.
    """
    
    def __init__(self, message: str, troubleshooting: Optional[list] = None):
        """
        Initialize LocalStack error.
        
        Args:
            message: Error message
            troubleshooting: Optional list of troubleshooting steps
        """
        self.message = message
        self.troubleshooting = troubleshooting or []
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format the error message with troubleshooting steps."""
        if not self.troubleshooting:
            return self.message
        
        steps = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(self.troubleshooting))
        return f"{self.message}\n\nTroubleshooting:\n{steps}"


class LocalStackConnectionError(LocalStackError):
    """
    Raised when LocalStack endpoint is unreachable.
    
    This error includes the endpoint URL that failed and provides
    specific troubleshooting guidance for connection issues.
    """
    
    def __init__(self, endpoint: str, original_error: Optional[Exception] = None):
        """
        Initialize LocalStack connection error.
        
        Args:
            endpoint: The LocalStack endpoint URL that failed
            original_error: The underlying exception that caused the failure
        """
        self.endpoint = endpoint
        self.original_error = original_error
        
        error_detail = str(original_error) if original_error else "Connection refused"
        
        message = f"Failed to connect to LocalStack at {endpoint}. Error: {error_detail}"
        
        troubleshooting = [
            f"Ensure LocalStack is running: docker ps | grep localstack",
            f"Check endpoint URL: curl {endpoint}/_localstack/health",
            "Verify port 4566 is not blocked by firewall",
            "Run: ./scripts/start-localstack.sh (Linux) or .\\scripts\\start-localstack.ps1 (Windows)",
            "Check LocalStack logs: docker logs starhub-localstack",
            "Ensure Docker is running and has sufficient resources"
        ]
        
        super().__init__(message, troubleshooting)


class LocalStackServiceError(LocalStackError):
    """
    Raised when a specific LocalStack service is unavailable or unhealthy.
    
    This error is raised when LocalStack is running but a specific service
    (e.g., DynamoDB, S3) is not available or returns an error.
    """
    
    def __init__(self, service: str, status: str, endpoint: Optional[str] = None):
        """
        Initialize LocalStack service error.
        
        Args:
            service: The AWS service name (e.g., 'dynamodb', 's3')
            status: The current status of the service
            endpoint: Optional endpoint URL
        """
        self.service = service
        self.status = status
        self.endpoint = endpoint
        
        message = f"LocalStack service '{service}' is not available (status: {status})"
        if endpoint:
            message += f" at {endpoint}"
        
        troubleshooting = [
            f"Check LocalStack health: curl http://localhost:4566/_localstack/health",
            f"Verify {service} is in SERVICES list in docker-compose-localstack.yml",
            "Restart LocalStack: docker-compose -f docker-compose-localstack.yml restart",
            f"Check LocalStack logs for {service} errors: docker logs starhub-localstack | grep -i {service}",
            "Ensure LocalStack has enough memory allocated in Docker"
        ]
        
        super().__init__(message, troubleshooting)


class LocalStackInitializationError(LocalStackError):
    """
    Raised when LocalStack resource initialization fails.
    
    This error is raised when creating DynamoDB tables, S3 buckets,
    or other resources in LocalStack fails.
    """
    
    def __init__(self, resource_type: str, resource_name: str, 
                 original_error: Optional[Exception] = None):
        """
        Initialize LocalStack initialization error.
        
        Args:
            resource_type: Type of resource (e.g., 'DynamoDB table', 'S3 bucket')
            resource_name: Name of the resource
            original_error: The underlying exception
        """
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.original_error = original_error
        
        error_detail = str(original_error) if original_error else "Unknown error"
        
        message = f"Failed to create {resource_type} '{resource_name}' in LocalStack. Error: {error_detail}"
        
        troubleshooting = [
            "Ensure LocalStack is running and healthy",
            "Check if the resource already exists (initialization should be idempotent)",
            "Verify AWS CLI is configured for LocalStack: aws --endpoint-url http://localhost:4566",
            "Run initialization script manually: ./scripts/localstack-init.sh",
            "Check LocalStack logs for detailed error: docker logs starhub-localstack"
        ]
        
        super().__init__(message, troubleshooting)


class LocalStackConfigurationError(LocalStackError):
    """
    Raised when LocalStack configuration is invalid.
    
    This error is raised when environment variables or configuration
    settings for LocalStack are invalid or inconsistent.
    """
    
    def __init__(self, config_key: str, config_value: str, reason: str):
        """
        Initialize LocalStack configuration error.
        
        Args:
            config_key: The configuration key that is invalid
            config_value: The invalid value
            reason: Explanation of why the value is invalid
        """
        self.config_key = config_key
        self.config_value = config_value
        self.reason = reason
        
        message = f"Invalid LocalStack configuration: {config_key}='{config_value}'. {reason}"
        
        troubleshooting = [
            "Check .env.localstack file for correct values",
            "Verify environment variables are set correctly",
            "See .env.localstack.example for valid configuration options",
            "Ensure USE_LOCALSTACK is set to 'true' (not 'yes', '1', etc.)"
        ]
        
        super().__init__(message, troubleshooting)
