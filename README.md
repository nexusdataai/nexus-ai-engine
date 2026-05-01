# nexus-ai-engine

Journey/stage/job AI orchestration engine extracted from `nexus-backend`.

Provides a pluggable core for transformation journeys, staged job execution, live
logging, reports, and SSE streaming. Storage is port-based: DynamoDB/S3 ships as
the default adapter; in-memory and custom adapters are supported.

## Status

**Pre-release (`0.1.0a1`).** The public API is not yet stable. Expect churn
during phases 2 through 9 of the extraction from
[`nexus-backend`](https://github.com/nexusdataai/nexus-backend) until `0.1.0`.

## Install

```bash
# From the internal Python index
pip install nexus-ai-engine

# Direct from GitHub (for pinning specific commits/tags)
pip install "nexus-ai-engine @ git+https://github.com/nexusdataai/nexus-ai-engine.git@main"

# Editable, side-by-side with nexus-backend during development
pip install -e /path/to/nexus-ai-engine
```

To include the AWS (DynamoDB/S3) default adapter and test utilities:

```bash
pip install "nexus-ai-engine[aws,test]"
```

## Package layout

```
src/nexus_ai_engine/
  config.py          # EngineConfig
  factory.py         # build_engine(...)
  errors.py          # Engine error hierarchy
  contracts/         # Protocol ports (repositories, sinks, events, scheduler, stage factory)
  models/            # Pydantic domain models (journey, prompt, logs/reports)
  stages/            # BaseStage contract, stage registry, PluginJourneyStage
  execution/         # TransformationJobExecutor, AsyncioJobScheduler
  services/          # JourneyService, PromptsService, LogsAndReportsService
  events/            # SSEManager / EventSink implementations
  adapters/          # DynamoDB, S3, in-memory shipped adapters
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,aws,test]"
pytest
```

## License

MIT. See [LICENSE](LICENSE).
