"""AWS adapters: client manager, LocalStack support."""

from .client_manager import (
    AWSClientManager,
    create_aws_client,
    create_aws_resource,
    get_default_client_manager,
    refresh_default_credentials,
    test_aws_credentials,
)
from .localstack_config import (
    LocalStackConfig,
    get_localstack_config,
    is_aws_environment,
    is_localstack_enabled,
    is_running_on_ecs,
    get_runtime_environment,
    reset_localstack_config,
)
from .localstack_errors import (
    LocalStackConfigurationError,
    LocalStackConnectionError,
    LocalStackError,
    LocalStackInitializationError,
    LocalStackServiceError,
)

__all__ = [
    "AWSClientManager",
    "LocalStackConfig",
    "LocalStackConfigurationError",
    "LocalStackConnectionError",
    "LocalStackError",
    "LocalStackInitializationError",
    "LocalStackServiceError",
    "create_aws_client",
    "create_aws_resource",
    "get_default_client_manager",
    "get_localstack_config",
    "get_runtime_environment",
    "is_aws_environment",
    "is_localstack_enabled",
    "is_running_on_ecs",
    "refresh_default_credentials",
    "reset_localstack_config",
    "test_aws_credentials",
]
