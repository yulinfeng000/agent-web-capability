# lightpanda-webfetch

LLM-friendly web fetch API powered by [Lightpanda](https://github.com/lightpanda-io/browser) headless browser.

## Prerequisites

- Python >= 3.14
- [Lightpanda](https://github.com/lightpanda-io/browser) binary installed and in `PATH`

### Install Lightpanda

```bash
scripts/install_lightpanda.sh
```

## Quick Start

```bash
pip install .
lpwf serve
```

Or without installing the CLI:

```bash
python main.py
```

Server starts at `http://0.0.0.0:8010` (configurable in `config.yaml`).

## CLI

| Command | Description |
|---------|-------------|
| `lpwf serve` | Start the web fetch server |
| `lpwf gen-token` | Generate a random API token |

### serve

```
lpwf serve [-c CONFIG]
```

Reads `host` and `port` from `config.yaml`. Use `-c` to specify an alternate config path.

### gen-token

```
lpwf gen-token
```

Outputs a token entry ready to paste into `config.yaml`:

```yaml
tokens:
  - token: "sk-lightpanda-xxxxxxxx"
    name: "my-app"
```

## Configuration

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8010

lightpanda:
  bin_path: "lightpanda"
  wait_ms: 2000
  obey_robots: false

fetch:
  timeout: 30
  max_concurrent: 5

tokens:
  - token: "sk-lightpanda-admin-key"
    name: "admin"
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `config.yaml` | Path to config file |
| `LIGHTPANDA_BIN` | `lightpanda` | Lightpanda binary path |
| `LIGHTPANDA_FETCH_TIMEOUT` | `30` | Fetch timeout in seconds |
| `LIGHTPANDA_MAX_CONCURRENT` | `5` | Max concurrent requests |
| `LIGHTPANDA_TOKENS` | - | Comma-separated API tokens |

Environment variables override their `config.yaml` counterparts.

## API

### `GET /fetch`

Fetch and render a web page.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `url` | _(required)_ | Page URL (must start with `http://` or `https://`) |
| `return_type` | `markdown` | Output format: `html`, `markdown`, or `plain_text` |

**Authentication:** `Authorization: Bearer <token>` header (required when tokens are configured).

```bash
# Markdown (default)
curl "http://localhost:8010/fetch?url=https://example.com" \
  -H "Authorization: Bearer sk-lightpanda-admin-key"

# HTML
curl "http://localhost:8010/fetch?url=https://example.com&return_type=html" \
  -H "Authorization: Bearer sk-lightpanda-admin-key"

# Plain text
curl "http://localhost:8010/fetch?url=https://example.com&return_type=plain_text" \
  -H "Authorization: Bearer sk-lightpanda-admin-key"
```

### `GET /health`

```bash
curl http://localhost:8010/health
```

## Docker

```bash
docker compose up -d
```

The container runs `lpwf serve`, picking up `config.yaml` from the mounted volume (`./config.yaml:/app/config.yaml:ro`).
