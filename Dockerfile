# Stage 1: Download lightpanda binary
FROM debian:bookworm-slim AS lightpanda
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
COPY scripts/install_lightpanda.sh /tmp/
RUN chmod +x /tmp/install_lightpanda.sh && /tmp/install_lightpanda.sh linux ${TARGETARCH}

# Stage 2: App runtime
FROM python:3.14-slim
COPY --from=lightpanda /usr/local/bin/lightpanda /usr/local/bin/lightpanda
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
CMD ["lpwf", "serve"]
