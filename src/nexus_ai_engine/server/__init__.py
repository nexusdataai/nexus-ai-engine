"""Reference server for the Nexus AI Engine.

Ships the canonical FastAPI app factory, MCP server, and `nexus-ai-engine serve`
CLI. The server is importable by host applications that prefer to mount the
library's routers in their own FastAPI instance; it is also runnable
standalone for local development, container images, and Kubernetes pods.

Routes are documented in docs/ROUTE_PARITY.md. Each router file starts with a
port-fidelity checklist citing the nexus-backend source lines to port per
phase of the extraction.
"""

from .app import create_app

__all__ = ["create_app"]
