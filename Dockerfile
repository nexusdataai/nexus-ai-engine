# Multi-stage build for the Nexus AI Engine reference server.
#
# Two image variants from the same Dockerfile, controlled by a build arg:
#
#   INCLUDE_TEST_DEPS=false   (default)  -> slim production image, [server] extras only
#   INCLUDE_TEST_DEPS=true               -> test image with [server,dev,test,harness]
#                                           plus tests/, Makefile, tox.ini, scripts/, docs/
#                                           so `kubectl exec -- make test-<tier>` works.
#
# Production target: <120 MB. Test target: ~250-300 MB.
# Conventions match nexus-backend/Dockerfile (python:3.12-slim, uid 1001, curl healthcheck).

# -----------------------------------------------------------------------------
# Stage 1: build dependencies into an isolated venv
# -----------------------------------------------------------------------------
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
COPY packages/nexus-tool-sdk ./packages/nexus-tool-sdk
COPY packages/tools-o2c ./packages/tools-o2c
# Test-only artifacts. Always copied into the build context (so the test
# build can use them) and conditionally retained in the final layer below.
COPY tests   ./tests-staged
COPY scripts ./scripts-staged
COPY docs    ./docs-staged
COPY Makefile tox.ini ./

RUN pip install --upgrade pip setuptools wheel && \
    pip install --prefer-binary "./packages/nexus-tool-sdk" "./packages/tools-o2c" && \
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

# -----------------------------------------------------------------------------
# Stage 2: slim runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

# `make` is included so the test image can run `make test-<tier>` via kubectl
# exec. It adds ~5 MB; production builds carry the same binary for parity.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends curl make \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean \
 && groupadd -g 1001 aiengine \
 && useradd -u 1001 -g aiengine -s /bin/sh -m aiengine \
 && mkdir -p /app/reports \
 && chown -R aiengine:aiengine /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=aiengine:aiengine /build /app

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
