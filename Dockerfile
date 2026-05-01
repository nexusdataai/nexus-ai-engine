# Multi-stage build for the Nexus AI Engine reference server.
# Target: <100MB final image. Mirrors the conventions of nexus-backend/Dockerfile
# (python:3.12-slim, non-root user uid 1001, healthcheck via curl).

# -----------------------------------------------------------------------------
# Stage 1: build dependencies into an isolated venv
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ \
 && rm -rf /var/lib/apt/lists/* \
 && python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip setuptools wheel \
 && pip install --prefer-binary ".[server]" \
 && find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
 && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
 && find /opt/venv -name "*.pyc" -delete 2>/dev/null || true \
 && find /opt/venv -name "*.pyo" -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: slim runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean \
 && groupadd -g 1001 aiengine \
 && useradd -u 1001 -g aiengine -s /bin/sh -m aiengine

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AWS_DEFAULT_REGION=us-east-1

WORKDIR /app
USER aiengine

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["nexus-ai-engine", "serve", "--http", "--host", "0.0.0.0", "--port", "8000"]
