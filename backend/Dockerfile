# Multi-stage build for the Nexus AI Engine reference server.
#
# Build from repo root:
#   docker build -f backend/Dockerfile -t nexus-ai-engine-api:local .
#
# Two image variants from the same Dockerfile, controlled by a build arg:
#
#   INCLUDE_TEST_DEPS=false   (default)  -> slim production image, [server] extras only
#   INCLUDE_TEST_DEPS=true               -> test image with [server,dev,test,harness]
#                                           plus tests/, Makefile, tox.ini, scripts/, docs/
#                                           so `kubectl exec -- make test-<tier>` works.

FROM python:3.12-slim AS builder

ARG INCLUDE_TEST_DEPS=false

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ \
 && rm -rf /var/lib/apt/lists/* \
 && python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY backend/src ./backend/src
COPY sdk/nexus-tool-sdk ./sdk/nexus-tool-sdk
COPY sdk/tools-o2c ./sdk/tools-o2c
COPY tests   ./tests-staged
COPY scripts ./scripts-staged
COPY docs ./docs-staged
COPY Makefile tox.ini ./

RUN pip install --upgrade pip setuptools wheel && \
    pip install --prefer-binary "./sdk/nexus-tool-sdk" "./sdk/tools-o2c" && \
    if [ "$INCLUDE_TEST_DEPS" = "true" ]; then \
        pip install --prefer-binary ".[server,dev,test,harness]" && \
        mv tests-staged tests && \
        mv scripts-staged scripts && \
        mv docs-staged docs; \
    else \
        pip install --prefer-binary ".[server]" && \
        rm -rf tests-staged scripts-staged docs-staged Makefile tox.ini; \
    fi && \
    find /opt/venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.pyc" -delete 2>/dev/null || true

FROM python:3.12-slim AS production

ARG VERSION=0.0.0
ARG BUILD_SHA=unknown

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends curl make \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean \
 && groupadd -g 1001 aiengine \
 && useradd -u 1001 -g aiengine -s /bin/sh -m aiengine \
 && mkdir -p /app/tests/reports \
 && chown -R aiengine:aiengine /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=aiengine:aiengine /build /app
COPY backend/VERSION /VERSION

ENV PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${VERSION} \
    GIT_SHA=${BUILD_SHA} \
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
