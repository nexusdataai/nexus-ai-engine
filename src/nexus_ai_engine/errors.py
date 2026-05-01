"""Error hierarchy for the Nexus AI Engine."""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all Nexus AI Engine errors."""


class ConfigurationError(EngineError):
    """Raised when EngineConfig is invalid or missing required values."""


class StageNotRegisteredError(EngineError):
    """Raised when a stage_id is requested that has not been registered."""


class JobCancelledError(EngineError):
    """Raised when a running job has been cancelled cooperatively."""


class RepositoryError(EngineError):
    """Raised by repository adapters when persistence operations fail."""
