"""`nexus-ai-engine` console script.

Boots either the FastAPI reference server or the MCP server. EngineConfig is
loaded from environment variables for now (matching nexus-backend's env var
contract); a future release may add ``--config path/to.yaml`` as well.

Commands:
    serve       Run the HTTP reference server.
    run-journey Execute a plugin-journey YAML end-to-end (uses the testing harness).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
    )


def _build_engine_config():
    """Construct an EngineConfig from environment variables.

    Every field falls back to sensible defaults so `nexus-ai-engine serve`
    works out of the box in a container with no env vars set (in-memory
    adapters will be used once build_engine is fully implemented).
    """
    from ..config import EngineConfig

    return EngineConfig(
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        role_arn=os.environ.get("AWS_ROLE_ARN"),
        dynamodb_transformation_table=os.environ.get("DYNAMODB_TRANSFORMATION_TABLE"),
        dynamodb_prompts_table=os.environ.get("DYNAMODB_PROMPTS_TABLE"),
        s3_journey_logs_bucket=os.environ.get("S3_JOURNEY_LOGS_BUCKET"),
        s3_journey_reports_bucket=os.environ.get("S3_JOURNEY_REPORTS_BUCKET"),
        max_concurrent_jobs=int(os.environ.get("MAX_CONCURRENT_JOBS", "10")),
    )


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .app import create_app

    engine = None
    try:
        from ..factory import build_engine  # not implemented yet

        engine = build_engine(_build_engine_config())
    except NotImplementedError:
        logging.getLogger(__name__).warning(
            "build_engine is not yet implemented; reference server starts without a wired engine. "
            "Routes will return 501 until phases 2-9 of the extraction plan complete."
        )
    except Exception as exc:
        logging.getLogger(__name__).exception("build_engine failed: %s", exc)
        return 1

    app = create_app(engine=engine, cors_origins=args.cors_origin or None)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        access_log=not args.no_access_log,
    )
    return 0


def _cmd_run_journey(args: argparse.Namespace) -> int:
    try:
        from ..testing import JourneyYAMLRunner
    except ImportError as exc:
        print(f"run-journey requires the harness extra: pip install 'nexus-ai-engine[harness]' ({exc})", file=sys.stderr)
        return 2

    runner = JourneyYAMLRunner()
    result = runner.run(args.path)
    print(result.summary())
    return 0 if result.ok else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexus-ai-engine")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the HTTP reference server")
    serve.add_argument("--http", action="store_true", default=True, help="Serve HTTP (default)")
    serve.add_argument("--host", default=os.environ.get("API_HOST", "0.0.0.0"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    serve.add_argument("--cors-origin", action="append", default=[], help="Allowed CORS origin (repeatable)")
    serve.add_argument("--no-access-log", action="store_true")
    serve.set_defaults(func=_cmd_serve)

    run = sub.add_parser("run-journey", help="Execute a plugin-journey YAML end-to-end")
    run.add_argument("path", help="Path to a plugin-journey YAML file")
    run.set_defaults(func=_cmd_run_journey)

    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
