# Nexus AI Engine — Backend

Python service package for journey orchestration, tool execution, and the reference FastAPI/MCP server.

## Layout

```text
backend/
├── VERSION
├── src/nexus_ai_engine/   # installable package (see root pyproject.toml)
└── README.md
```

Install from the repository root:

```bash
pip install -e ".[dev,server,test,harness]"
```

See [docs/spec/002-repository-structure.md](../docs/spec/002-repository-structure.md) for the target monorepo layout.
