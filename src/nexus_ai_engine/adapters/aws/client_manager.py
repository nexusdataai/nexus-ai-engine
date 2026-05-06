"""
AWS Client Utilities for TMF ODA Transformer

This module provides utilities for creating AWS clients with auto-refreshing credentials.
Supports both real AWS and LocalStack for local development.
"""

import boto3
import os
import json
from typing import Optional, Dict, Any
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session
from datetime import datetime, timedelta, timezone
import logging

# Try to import python-dotenv, but don't fail if it's not available
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Import LocalStack configuration and errors
from .localstack_config import LocalStackConfig, get_localstack_config
from .localstack_errors import LocalStackConnectionError, LocalStackServiceError

logger = logging.getLogger(__name__)

# Credential refresh buffer - refresh 5 minutes before expiry
_REFRESH_BUFFER_MINUTES = 5


def _load_env_config() -> Dict[str, Optional[str]]:
    """
    Load configuration from environment variables.
    
    AWS credentials are NOT loaded from .env files - they come from:
    - On ECS: Task role (automatic via instance metadata)
    - Locally: ~/.aws/credentials (set by aws-login.sh)
    
    Only USE_LOCALSTACK and related settings are read from .env files.
    """
    config = {}
    
    # Get configuration values from environment only
    # AWS credentials/region come from boto3's default credential chain:
    # - ECS task role
    # - ~/.aws/credentials and ~/.aws/config (set by aws-login.sh)
    config['role_arn'] = os.environ.get('AWS_ROLE_ARN')
    config['region'] = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')  # Read from env, fall back to boto3 default
    config['profile'] = os.environ.get('AWS_PROFILE')
    
    return config


class AWSClientManager:
    """
    Manages AWS client creation with support for role assumption and auto-refreshing credentials.
    
    Uses botocore's RefreshableCredentials to automatically refresh assumed role credentials
    before they expire, enabling long-running server processes to maintain valid AWS sessions.
    
    Also supports LocalStack for local development - when USE_LOCALSTACK=true, all clients
    are configured to use LocalStack endpoints with dummy credentials.
    """
    
    def __init__(self, role_arn: Optional[str] = None, region_name: Optional[str] = None):
        """Initialize the AWS client manager."""
        # Load LocalStack configuration first
        self.localstack_config = get_localstack_config()
        
        # Load configuration from environment and .env file
        env_config = _load_env_config()
        
        # In LocalStack mode, ignore role_arn and use LocalStack settings
        if self.localstack_config.enabled:
            self.role_arn = None  # No role assumption in LocalStack
            self.region_name = self.localstack_config.region
            self.profile = None
            logger.info(f"LocalStack mode enabled - endpoint: {self.localstack_config.endpoint_url}")
            logger.info(f"LocalStack region: {self.region_name}")
        else:
            self.role_arn = role_arn or env_config['role_arn']
            self.region_name = region_name or env_config['region'] or self._get_default_region()
            self.profile = env_config['profile']
            
            # Log the configuration
            if self.role_arn:
                logger.info(f"AWS Client Manager configured with role ARN: {self.role_arn} (auto-refresh enabled)")
            else:
                logger.info("AWS Client Manager configured with default credential chain")
            logger.info(f"AWS Region: {self.region_name}")
            if self.profile:
                logger.info(f"AWS Profile: {self.profile}")
        
        self._session = None  # Cached session with refreshable credentials
    
    def _get_default_region(self) -> str:
        """Get the default AWS region."""
        # Try boto3 session default region
        try:
            session = boto3.Session()
            region = session.region_name
            if region:
                return region
        except Exception:
            pass
        
        # Fallback to us-east-2
        return 'us-east-2'
    
    def _test_instance_role(self) -> bool:
        """Test if instance role is available (EC2/ECS/Lambda)."""
        try:
            # Try to get credentials from instance metadata
            session = boto3.Session(region_name=self.region_name)
            sts_client = session.client('sts')
            
            # This will use instance role if available
            identity = sts_client.get_caller_identity()
            
            # Check if this is an instance role (contains 'instance' or role path)
            arn = identity.get('Arn', '')
            if 'assumed-role' in arn and any(keyword in arn.lower() for keyword in ['instance', 'ec2', 'ecs', 'lambda']):
                logger.info(f"Instance role detected: {arn}")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Instance role test failed: {str(e)}")
            return False
    
    def _assume_role_and_get_credentials(self) -> Dict[str, Any]:
        """
        Assume the configured role and return credentials in RefreshableCredentials format.
        
        This method creates a fresh boto3 session each time to pick up any updated credentials
        from the environment or credential files.
        
        Returns:
            Dict with access_key, secret_key, token, and expiry_time
        """
        if not self.role_arn:
            raise ValueError("Role ARN is required for role assumption")
        
        try:
            # Create unique session name for this refresh
            session_name = f"TMF-ODA-Transformer-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            logger.info(f"Assuming/refreshing role: {self.role_arn}")
            
            # IMPORTANT: Create a fresh boto3 Session to pick up updated credentials from the credential file
            # This allows the gateway to use new credentials after aws-login.sh is run
            session_kwargs = {'region_name': self.region_name}
            if self.profile:
                session_kwargs['profile_name'] = self.profile
            
            # Create a new session (not cached) to pick up refreshed credentials
            fresh_session = boto3.Session(**session_kwargs)
            sts_client = fresh_session.client('sts')
            
            # Assume the role with 1-hour duration
            response = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName=session_name,
                DurationSeconds=3600  # 1 hour
            )
            
            credentials = response['Credentials']
            expiry_time = credentials['Expiration']
            
            # Ensure expiry_time is timezone-aware
            if expiry_time.tzinfo is None:
                expiry_time = expiry_time.replace(tzinfo=timezone.utc)
            
            logger.info(f"Successfully assumed role: {self.role_arn}, expires: {expiry_time.isoformat()}")
            
            # Return in the format RefreshableCredentials expects
            return {
                'access_key': credentials['AccessKeyId'],
                'secret_key': credentials['SecretAccessKey'],
                'token': credentials['SessionToken'],
                'expiry_time': expiry_time
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            
            # If base credentials are expired, log a helpful message
            if error_code in ['ExpiredToken', 'ExpiredTokenException']:
                logger.error(f"Base AWS credentials have expired. Please run aws-login.sh to refresh credentials.")
                logger.error(f"After running aws-login.sh, restart the gateway with: ./gateway.sh restart")
            
            logger.error(f"Failed to assume role {self.role_arn}: {error_code} - {error_msg}")
            raise Exception(f"Role assumption failed: {error_code} - {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error assuming role {self.role_arn}: {str(e)}")
            raise Exception(f"Role assumption failed: {str(e)}")
    
    def _create_refreshable_session(self) -> boto3.Session:
        """
        Create a boto3 session with RefreshableCredentials that auto-refresh before expiry.
        
        This ensures long-running processes maintain valid credentials without manual intervention.
        """
        # Get initial credentials
        creds_dict = self._assume_role_and_get_credentials()
        
        # Create RefreshableCredentials
        # The refresh_using callable will be called automatically when credentials are about to expire
        refreshable_credentials = RefreshableCredentials.create_from_metadata(
            metadata=creds_dict,
            refresh_using=self._assume_role_and_get_credentials,
            method='sts-assume-role'
        )
        
        # Create a botocore session and set the refreshable credentials
        botocore_session = get_session()
        botocore_session._credentials = refreshable_credentials
        botocore_session.set_config_variable('region', self.region_name)
        
        # Create boto3 session from botocore session
        session = boto3.Session(botocore_session=botocore_session, region_name=self.region_name)
        
        logger.info("Created session with auto-refreshing credentials")
        return session
    
    def _is_running_under_irsa(self) -> bool:
        """
        Check if running under IRSA (IAM Roles for Service Accounts).
        
        IRSA is detected by the presence of the web identity token file
        and the AWS_WEB_IDENTITY_TOKEN_FILE environment variable.
        """
        import os
        token_file = os.environ.get('AWS_WEB_IDENTITY_TOKEN_FILE')
        if token_file and os.path.exists(token_file):
            logger.info(f"IRSA detected: web identity token at {token_file}")
            return True
        return False
    
    def _create_session(self) -> boto3.Session:
        """Create a boto3 session with appropriate credentials."""
        # If LocalStack mode is enabled, use LocalStack session
        if self.localstack_config.enabled:
            return self._create_localstack_session()
        
        # Check if running under IRSA - if so, use default credential chain
        # IRSA provides credentials automatically, no need for manual role assumption
        if self._is_running_under_irsa():
            logger.info("Running under IRSA - using web identity credentials (auto-refresh by AWS SDK)")
            session_kwargs = {'region_name': self.region_name}
            return boto3.Session(**session_kwargs)
        
        # If role ARN is specified and NOT under IRSA, use refreshable credentials
        if self.role_arn:
            # Use cached session if available (it has refreshable credentials)
            if self._session is not None:
                return self._session
            
            # Create session with auto-refreshing credentials
            self._session = self._create_refreshable_session()
            return self._session
        else:
            # For non-role-based auth, create a normal session
            session_kwargs = {'region_name': self.region_name}
            
            # Try instance role first, then fall back to default chain
            if self._test_instance_role():
                logger.info("Using instance role credentials (auto-refresh by AWS SDK)")
                # No additional setup needed - boto3 will auto-detect and auto-refresh
            else:
                logger.info("Using default credential chain")
                if self.profile:
                    session_kwargs['profile_name'] = self.profile
            
            return boto3.Session(**session_kwargs)
    
    def _create_localstack_session(self) -> boto3.Session:
        """
        Create a boto3 session configured for LocalStack.
        
        Uses dummy credentials since LocalStack doesn't require real AWS credentials.
        """
        return boto3.Session(
            aws_access_key_id=self.localstack_config.access_key,
            aws_secret_access_key=self.localstack_config.secret_key,
            region_name=self.localstack_config.region
        )
    
    def invalidate_session(self):
        """
        Invalidate the cached session, forcing recreation on next client creation.
        
        This is useful when base credentials have been refreshed externally (e.g., via aws-login.sh)
        and you want the gateway to pick up the new credentials without restarting.
        """
        logger.info("Invalidating cached AWS session - will recreate with fresh credentials on next use")
        self._session = None
    
    def refresh_credentials(self):
        """
        Force refresh of AWS credentials by invalidating the cached session.
        
        This will cause the next client creation to:
        1. Read fresh credentials from the credential file
        2. Assume the role with those fresh credentials
        3. Create a new RefreshableCredentials session
        """
        logger.info("Forcing credential refresh")
        self.invalidate_session()
        
        # Try to create a new session immediately to verify credentials work
        try:
            session = self._create_session()
            # Test the credentials by making a simple STS call
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"Successfully refreshed credentials for: {identity['Arn']}")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {str(e)}")
            return False
    
    def create_client(self, service_name: str, config: Optional[Config] = None, retry_on_expired: bool = True) -> Any:
        """
        Create an AWS service client with auto-refreshing credentials.
        
        In LocalStack mode, the client is configured to use LocalStack endpoints.
        
        Args:
            service_name: AWS service name (e.g., 'dynamodb', 's3')
            config: Optional botocore Config object
            retry_on_expired: If True, will attempt to refresh credentials if they're expired
        """
        try:
            # LocalStack mode - use LocalStack endpoint
            if self.localstack_config.enabled:
                return self._create_localstack_client(service_name, config)
            
            session = self._create_session()
            
            # Create default config if none provided
            if config is None:
                config = Config(
                    retries={'max_attempts': 3, 'mode': 'adaptive'},
                    user_agent_extra='TMF-ODA-Transformer/1.0'
                )
            
            client = session.client(service_name, config=config)
            logger.debug(f"Created {service_name} client successfully")
            return client
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # If credentials are expired and we haven't retried yet, try refreshing
            if error_code in ['ExpiredToken', 'ExpiredTokenException'] and retry_on_expired:
                logger.warning(f"Credentials expired while creating {service_name} client, attempting refresh...")
                self.invalidate_session()
                # Retry once with refreshed credentials
                return self.create_client(service_name, config, retry_on_expired=False)
            
            logger.error(f"Failed to create {service_name} client: {error_code}")
            raise Exception(f"Failed to create {service_name} client: {error_code}")
            
        except Exception as e:
            # In LocalStack mode, provide more helpful error messages
            if self.localstack_config.enabled:
                raise LocalStackConnectionError(
                    endpoint=self.localstack_config.endpoint_url,
                    original_error=e
                )
            logger.error(f"Failed to create {service_name} client: {str(e)}")
            raise Exception(f"Failed to create {service_name} client: {str(e)}")
    
    def _create_localstack_client(self, service_name: str, config: Optional[Config] = None) -> Any:
        """
        Create an AWS service client configured for LocalStack.
        
        Args:
            service_name: AWS service name (e.g., 'dynamodb', 's3')
            config: Optional botocore Config object
        """
        try:
            session = self._create_localstack_session()
            
            # Create default config if none provided
            if config is None:
                config = Config(
                    retries={'max_attempts': 3, 'mode': 'standard'},
                    user_agent_extra='TMF-ODA-Transformer/1.0-LocalStack'
                )
            
            endpoint_url = self.localstack_config.get_service_endpoint(service_name)
            
            client = session.client(
                service_name,
                endpoint_url=endpoint_url,
                config=config,
                use_ssl=False,
                verify=False
            )
            
            logger.debug(f"Created LocalStack {service_name} client at {endpoint_url}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create LocalStack {service_name} client: {str(e)}")
            raise LocalStackConnectionError(
                endpoint=self.localstack_config.endpoint_url,
                original_error=e
            )
    
    def create_resource(self, service_name: str, config: Optional[Config] = None, retry_on_expired: bool = True) -> Any:
        """
        Create an AWS service resource with auto-refreshing credentials.
        
        In LocalStack mode, the resource is configured to use LocalStack endpoints.
        
        Args:
            service_name: AWS service name (e.g., 'dynamodb', 's3')
            config: Optional botocore Config object
            retry_on_expired: If True, will attempt to refresh credentials if they're expired
        """
        try:
            # LocalStack mode - use LocalStack endpoint
            if self.localstack_config.enabled:
                return self._create_localstack_resource(service_name, config)
            
            session = self._create_session()
            
            # Create default config if none provided
            if config is None:
                config = Config(
                    retries={'max_attempts': 3, 'mode': 'adaptive'},
                    user_agent_extra='TMF-ODA-Transformer/1.0'
                )
            
            resource = session.resource(service_name, config=config)
            logger.debug(f"Created {service_name} resource successfully")
            return resource
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # If credentials are expired and we haven't retried yet, try refreshing
            if error_code in ['ExpiredToken', 'ExpiredTokenException'] and retry_on_expired:
                logger.warning(f"Credentials expired while creating {service_name} resource, attempting refresh...")
                self.invalidate_session()
                # Retry once with refreshed credentials
                return self.create_resource(service_name, config, retry_on_expired=False)
            
            logger.error(f"Failed to create {service_name} resource: {error_code}")
            raise Exception(f"Failed to create {service_name} resource: {error_code}")
            
        except Exception as e:
            # In LocalStack mode, provide more helpful error messages
            if self.localstack_config.enabled:
                raise LocalStackConnectionError(
                    endpoint=self.localstack_config.endpoint_url,
                    original_error=e
                )
            logger.error(f"Failed to create {service_name} resource: {str(e)}")
            raise Exception(f"Failed to create {service_name} resource: {str(e)}")
    
    def _create_localstack_resource(self, service_name: str, config: Optional[Config] = None) -> Any:
        """
        Create an AWS service resource configured for LocalStack.
        
        Args:
            service_name: AWS service name (e.g., 'dynamodb', 's3')
            config: Optional botocore Config object
        """
        try:
            session = self._create_localstack_session()
            
            # Create default config if none provided
            if config is None:
                config = Config(
                    retries={'max_attempts': 3, 'mode': 'standard'},
                    user_agent_extra='TMF-ODA-Transformer/1.0-LocalStack'
                )
            
            endpoint_url = self.localstack_config.get_service_endpoint(service_name)
            
            resource = session.resource(
                service_name,
                endpoint_url=endpoint_url,
                config=config,
                use_ssl=False,
                verify=False
            )
            
            logger.debug(f"Created LocalStack {service_name} resource at {endpoint_url}")
            return resource
            
        except Exception as e:
            logger.error(f"Failed to create LocalStack {service_name} resource: {str(e)}")
            raise LocalStackConnectionError(
                endpoint=self.localstack_config.endpoint_url,
                original_error=e
            )
    
    def test_credentials(self) -> Dict[str, Any]:
        """Test the current credentials and return caller identity."""
        try:
            session = self._create_session()
            sts_client = session.client('sts')
            
            identity = sts_client.get_caller_identity()
            logger.info(f"Credentials test successful - Account: {identity['Account']}, ARN: {identity['Arn']}")
            return identity
            
        except Exception as e:
            logger.error(f"Credentials test failed: {str(e)}")
            raise Exception(f"Credentials test failed: {str(e)}")
    
    def test_localstack_connection(self) -> Dict[str, Any]:
        """
        Test LocalStack connectivity and return service status.
        
        Returns:
            Dictionary with:
                - enabled: Whether LocalStack mode is enabled
                - healthy: Whether LocalStack is responding
                - endpoint: LocalStack endpoint URL
                - services: Service name -> status mapping
                - error: Error message if unhealthy
        """
        if not self.localstack_config.enabled:
            return {
                "enabled": False,
                "message": "LocalStack mode is not enabled. Set USE_LOCALSTACK=true to enable."
            }
        
        import requests
        
        try:
            health_url = f"{self.localstack_config.endpoint_url}/_localstack/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                health_data = response.json()
                services = health_data.get('services', {})
                
                return {
                    "enabled": True,
                    "healthy": True,
                    "endpoint": self.localstack_config.endpoint_url,
                    "services": services,
                    "region": self.localstack_config.region
                }
            else:
                return {
                    "enabled": True,
                    "healthy": False,
                    "endpoint": self.localstack_config.endpoint_url,
                    "error": f"Health check returned status {response.status_code}"
                }
                
        except requests.exceptions.ConnectionError as e:
            return {
                "enabled": True,
                "healthy": False,
                "endpoint": self.localstack_config.endpoint_url,
                "error": f"Connection refused - LocalStack may not be running",
                "troubleshooting": [
                    "Start LocalStack: ./scripts/start-localstack.sh",
                    "Check Docker: docker ps | grep localstack",
                    f"Verify endpoint: curl {self.localstack_config.endpoint_url}/_localstack/health"
                ]
            }
        except requests.exceptions.Timeout:
            return {
                "enabled": True,
                "healthy": False,
                "endpoint": self.localstack_config.endpoint_url,
                "error": "Connection timeout - LocalStack may be starting up"
            }
        except Exception as e:
            return {
                "enabled": True,
                "healthy": False,
                "endpoint": self.localstack_config.endpoint_url,
                "error": str(e)
            }


# Global instance for backward compatibility
_default_client_manager = None


def get_default_client_manager() -> AWSClientManager:
    """Get the default AWS client manager instance."""
    global _default_client_manager
    if _default_client_manager is None:
        _default_client_manager = AWSClientManager()
    return _default_client_manager


def refresh_default_credentials() -> bool:
    """
    Refresh the default AWS client manager's credentials.
    
    This is useful when base credentials have been refreshed externally (e.g., via aws-login.sh)
    and you want to pick up the new credentials without restarting the process.
    
    Returns:
        bool: True if refresh was successful, False otherwise
    """
    global _default_client_manager
    if _default_client_manager is not None:
        return _default_client_manager.refresh_credentials()
    else:
        logger.warning("No default client manager exists yet, will create fresh on next use")
        return True


def create_aws_client(service_name: str, 
                     role_arn: Optional[str] = None, 
                     region_name: Optional[str] = None,
                     config: Optional[Config] = None) -> Any:
    """Create an AWS service client with optional role assumption and auto-refresh."""
    client_manager = AWSClientManager(role_arn=role_arn, region_name=region_name)
    return client_manager.create_client(service_name, config=config)


def create_aws_resource(service_name: str, 
                       role_arn: Optional[str] = None, 
                       region_name: Optional[str] = None,
                       config: Optional[Config] = None) -> Any:
    """Create an AWS service resource with optional role assumption and auto-refresh."""
    client_manager = AWSClientManager(role_arn=role_arn, region_name=region_name)
    return client_manager.create_resource(service_name, config=config)


def test_aws_credentials(role_arn: Optional[str] = None, 
                        region_name: Optional[str] = None) -> Dict[str, Any]:
    """Test AWS credentials with optional role assumption."""
    client_manager = AWSClientManager(role_arn=role_arn, region_name=region_name)
    return client_manager.test_credentials()
