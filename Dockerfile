# Stage 1: Download lightpanda binary
FROM debian:bookworm-slim AS lightpanda
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
COPY scripts/install_lightpanda.sh /tmp/
RUN chmod +x /tmp/install_lightpanda.sh && /tmp/install_lightpanda.sh linux ${TARGETARCH}

# Stage 2: App runtime
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=lightpanda /usr/local/bin/lightpanda /usr/local/bin/lightpanda
WORKDIR /app

# Phase 1: install dependencies only (cached until pyproject.toml or uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Phase 2: copy source and install the project itself (fast, re-runs on source change)
COPY . .
RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_MOUNT=1
CMD ["awc", "serve"]
