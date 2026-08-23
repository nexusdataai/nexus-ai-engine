"""Ontology API errors for nexus-tool-sdk."""

from __future__ import annotations

from typing import Any


class OntologyError(Exception):
    """Base error for VDL / Connector HTTP failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.details = details or {}


class VdlError(OntologyError):
    """VDL query failure."""


class ConnectorError(OntologyError):
    """Connector invoke failure."""
