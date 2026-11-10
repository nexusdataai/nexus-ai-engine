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

    Table and bucket names fall back to CAPABILITY_NAME + ENVIRONMENT driven
    resource naming when explicit DYNAMODB_* / S3_* vars are unset.
    Host dev loads backend/.env.local via Makefile (python-dotenv), not here.
    """
    from ..config import config_from_environment

    return config_from_environment()


# Mapping of EngineConfig field names → environment variable names used as
# fallbacks when a key is absent from SSM. Keeping this in one place so the
# unit test can introspect the contract.
_SSM_TO_ENV_FALLBACK = {
    "role_arn":                       "AWS_ROLE_ARN",
    "dynamodb_transformation_table":  "DYNAMODB_TRANSFORMATION_TABLE",
    "dynamodb_executions_table":      "DYNAMODB_EXECUTIONS_TABLE",
    "dynamodb_prompts_table":         "DYNAMODB_PROMPTS_TABLE",
    "s3_journey_logs_bucket":         "S3_JOURNEY_LOGS_BUCKET",
    "s3_journey_reports_bucket":      "S3_JOURNEY_REPORTS_BUCKET",
    "max_concurrent_jobs":            "MAX_CONCURRENT_JOBS",
    "redis_url":                      "REDIS_URL",
    "job_stream_key":                 "JOB_STREAM_KEY",
    "job_consumer_group":             "JOB_CONSUMER_GROUP",
    "job_execution_mode":             "JOB_EXECUTION_MODE",
    "max_global_jobs":                "MAX_GLOBAL_JOBS",
    "sse_redis_enabled":              "SSE_REDIS_ENABLED",
    "capability_name":                "CAPABILITY_NAME",
    "environment":                    "ENVIRONMENT",
}


def _build_engine_config_from_ssm(prefix: str):
    """Construct an EngineConfig from AWS SSM Parameter Store.

    Reads every parameter under ``prefix`` (e.g. ``/ai-engine/dev/``) and
    maps the leaf key (last path segment) to the matching ``EngineConfig``
    field. Falls back to the corresponding environment variable for any
    field that is not present in SSM, so an operator can provide overrides
    without round-tripping through SSM.

    Requires ``ssm:GetParametersByPath`` on the prefix; the IAM policy at
    ``scripts/legacy-deploy/iam/ai-engine-policy.json`` already grants this on
    ``arn:aws:ssm:*:*:parameter/ai-engine/*``.

    Args:
        prefix: The SSM parameter path prefix to scan (must end with ``/``
            for ``get_parameters_by_path`` recursion to behave intuitively).

    Returns:
        A populated :class:`EngineConfig`.
    """
    import boto3

    from ..adapters.aws.localstack_config import LocalStackConfig
    from ..config import EngineConfig

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    ssm_kwargs: dict = {"region_name": region}
    ssm_endpoint = LocalStackConfig.from_environment().get_service_endpoint("ssm")
    if ssm_endpoint:
        ssm_kwargs["endpoint_url"] = ssm_endpoint
        ssm_kwargs.setdefault("aws_access_key_id", os.environ.get("AWS_ACCESS_KEY_ID", "test"))
        ssm_kwargs.setdefault("aws_secret_access_key", os.environ.get("AWS_SECRET_ACCESS_KEY", "test"))
    ssm = boto3.client("ssm", **ssm_kwargs)
    params: dict[str, str] = {}
    paginator = ssm.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=prefix, Recursive=True, WithDecryption=True):
        for p in page.get("Parameters", []):
            key = p["Name"].rsplit("/", 1)[-1]
            params[key] = p["Value"]

    logging.getLogger(__name__).info(
        "Loaded %d parameters from SSM prefix %s", len(params), prefix
    )

    def _ssm_or_env(field: str):
        env_key = _SSM_TO_ENV_FALLBACK.get(field)
        v = params.get(field)
        if v is not None:
            return v
        if env_key:
            return os.environ.get(env_key)
        return None

    return EngineConfig(
        region=region,
        role_arn=_ssm_or_env("role_arn"),
        dynamodb_transformation_table=_ssm_or_env("dynamodb_transformation_table"),
        dynamodb_executions_table=_ssm_or_env("dynamodb_executions_table"),
        dynamodb_prompts_table=_ssm_or_env("dynamodb_prompts_table"),
        s3_journey_logs_bucket=_ssm_or_env("s3_journey_logs_bucket"),
        s3_journey_reports_bucket=_ssm_or_env("s3_journey_reports_bucket"),
        max_concurrent_jobs=int(_ssm_or_env("max_concurrent_jobs") or "10"),
        redis_url=_ssm_or_env("redis_url"),
        job_stream_key=_ssm_or_env("job_stream_key") or "ai-engine:jobs",
        job_consumer_group=_ssm_or_env("job_consumer_group") or "ai-engine-workers",
        job_execution_mode=(
            "queue"
            if str(_ssm_or_env("job_execution_mode") or "inline").lower() == "queue"
            else "inline"
        ),
        max_global_jobs=int(_ssm_or_env("max_global_jobs") or _ssm_or_env("max_concurrent_jobs") or "50"),
        sse_redis_enabled=str(_ssm_or_env("sse_redis_enabled") or "true").lower()
        not in ("0", "false", "no"),
        capability_name=_ssm_or_env("capability_name") or "ai-engine",
        environment=_ssm_or_env("environment") or "dev",
    )


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .app import create_app

    engine = None
    try:
        from ..factory import build_engine  # not implemented yet

        # If the operator passed --ssm-prefix (or SSM_PARAMETER_PREFIX env),
        # bootstrap EngineConfig from SSM Parameter Store; otherwise fall
        # back to the existing env-var loader so the in-memory dev path
        # stays AWS-free.
        if getattr(args, "ssm_prefix", None):
            config = _build_engine_config_from_ssm(args.ssm_prefix)
        else:
            config = _build_engine_config()
        engine = build_engine(config)
    except NotImplementedError:
        logging.getLogger(__name__).warning(
            "build_engine is not yet implemented; reference server starts without a wired engine. "
            "Routes will return 501 until phases 2-9 of the extraction plan complete."
        )
    except Exception as exc:
        logging.getLogger(__name__).exception("build_engine failed: %s", exc)
        return 1

    # Optionally register the synthetic demo stages shipped with the
    # library. Default-on for `serve` (the standalone deploy use case)
    # so a fresh pod has runnable stage_ids out of the box for
    # performance / smoke testing. Embedding hosts that import the
    # library directly opt in via `register_demo_stages()` themselves.
    if getattr(args, "register_demo_stages", True):
        try:
            from ..stages import register_demo_stages
            registered = register_demo_stages()
            logging.getLogger(__name__).info(
                "Registered %d demo stages: %s", len(registered), ", ".join(registered)
            )
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Demo stage registration failed: %s", exc
            )

    try:
        from ..stages import register_job_archival_stage

        register_job_archival_stage()
        logging.getLogger(__name__).info("Registered job_archival stage")
    except Exception as exc:
        logging.getLogger(__name__).exception("job_archival registration failed: %s", exc)

    app = create_app(engine=engine, cors_origins=args.cors_origin or None)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        access_log=not args.no_access_log,
    )
    return 0


def _cmd_print_demo_journeys(args: argparse.Namespace) -> int:
    """Emit the canonical demo-journey definitions as JSON.

    Used by `scripts/seed-sample-journeys.sh` so the bash script and the
    runtime stage registry both read from the same source. Print-only,
    no AWS / engine wiring required.
    """
    import json

    from ..stages import DEMO_JOURNEYS

    print(json.dumps(DEMO_JOURNEYS, indent=2))
    return 0


def _cmd_worker(args: argparse.Namespace) -> int:
    from ..workers.job_worker import main as worker_main

    worker_main()
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


def _cmd_run_agent(args: argparse.Namespace) -> int:
    print(
        "run-agent moved to switchpoint-prototype/runtime. "
        "Use: switchpoint-runtime or pip install -e switchpoint-prototype/runtime",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexus-ai-engine")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser(
        "serve",
        help="Run the HTTP reference server (host dev: load backend/.env.local via Makefile)",
    )
    serve.add_argument("--http", action="store_true", default=True, help="Serve HTTP (default)")
    serve.add_argument("--host", default=os.environ.get("API_HOST", "0.0.0.0"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    serve.add_argument("--cors-origin", action="append", default=[], help="Allowed CORS origin (repeatable)")
    serve.add_argument("--no-access-log", action="store_true")
    serve.add_argument(
        "--ssm-prefix",
        default=os.environ.get("SSM_PARAMETER_PREFIX"),
        help=(
            "If set, bootstrap EngineConfig from this SSM Parameter Store path "
            "(e.g. /ai-engine/dev/). Per-key environment variables act as "
            "fallbacks for any key absent from SSM. Requires ssm:GetParametersByPath "
            "on the prefix. When unset, EngineConfig is built from environment "
            "variables only (legacy behaviour)."
        ),
    )
    # Demo stages are useful for performance / smoke testing the standalone
    # deploy when no host application has registered domain stages. Default
    # ON for `serve` so a fresh pod is immediately runnable; embedding
    # hosts that import the library directly should leave them off and
    # call `nexus_ai_engine.stages.register_demo_stages()` explicitly.
    _demo_default = os.environ.get("REGISTER_DEMO_STAGES", "true").lower() not in (
        "0", "false", "no", "off", ""
    )
    serve.add_argument(
        "--register-demo-stages",
        dest="register_demo_stages",
        action="store_true",
        default=_demo_default,
        help=(
            "Register the synthetic demo stages bundled with the library "
            "(order_to_cash, call_ingest, transcribe, analyze, demand_forecast, "
            "inventory_opt, supply_risk). Each step does bounded synthetic work "
            "(random sleep + emit_log per tick). Default: on. "
            "Set REGISTER_DEMO_STAGES=false to disable, or pass --no-register-demo-stages."
        ),
    )
    serve.add_argument(
        "--no-register-demo-stages",
        dest="register_demo_stages",
        action="store_false",
        help="Disable demo stage registration (overrides REGISTER_DEMO_STAGES env).",
    )
    serve.set_defaults(func=_cmd_serve)

    run = sub.add_parser("run-journey", help="Execute a plugin-journey YAML end-to-end")
    run.add_argument("path", help="Path to a plugin-journey YAML file")
    run.set_defaults(func=_cmd_run_journey)

    agent = sub.add_parser("run-agent", help="Debug embedded agent runtime (SDK owns LLM)")
    agent.add_argument("--plugin", required=True, help="Path to plugin root")
    agent.add_argument("--agent", required=True, help="Agent name")
    agent.add_argument("--task", default="Run mission", help="Task description")
    agent.set_defaults(func=_cmd_run_agent)

    pdj = sub.add_parser(
        "print-demo-journeys",
        help="Print the bundled demo journey definitions as JSON (used by seed scripts)",
    )
    pdj.set_defaults(func=_cmd_print_demo_journeys)

    worker = sub.add_parser("worker", help="Run Redis Streams job worker process")
    worker.set_defaults(func=_cmd_worker)

    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
