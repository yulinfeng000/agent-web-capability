# agent-web-capability

Web capability API for AI agents — **fetch** any web page via [Lightpanda](https://github.com/lightpanda-io/browser) headless browser and **search** the web via multiple providers.

## Prerequisites

- Python >= 3.14
- [Lightpanda](https://github.com/lightpanda-io/browser) binary installed and in `PATH`
- (Optional) Search provider API keys: Tavily, Brave, or SerpAPI

### Install Lightpanda

```bash
scripts/install_lightpanda.sh
```

## Quick Start

```bash
# Install with DuckDuckGo search (free, no API key)
pip install .

# Or with all search providers
pip install ".[all]"

# Start the server
awc serve
```

Server starts at `http://0.0.0.0:8010` (configurable in `config.yaml`).

## CLI

| Command | Description |
|---------|-------------|
| `awc serve` | Start the web capability server (fetch + search) |
| `awc gen-token` | Generate a random API token |
| `awc mcp-serve` | Start MCP server in stdio mode (for Claude Desktop) |
| `awc mcp-serve-http` | Start MCP server in Streamable HTTP mode |

### serve

```
awc serve [-c CONFIG]
```

Reads `host` and `port` from `config.yaml`. Use `-c` to specify an alternate config path.

### gen-token

```
awc gen-token [name]
```

Outputs a token entry ready to paste into `config.yaml`:

```yaml
tokens:
  - token: "sk-xxxxxxxx"
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
  capacity_wait_timeout: 5
  max_concurrent: 5
  default_return_type: "markdown"
  block_private_networks: true       # Block internal/private destinations
  max_response_size: 10485760        # 10 MiB
  v8_max_heap_mb: 256

search:
  default_engine: "duckduckgo"    # Default search engine
  default_format: "json"          # Default response format (json or csv)
  default_num_results: 5          # Default result count (max 50)
  timeout: 20
  capacity_wait_timeout: 5
  max_concurrent: 10
  tavily_api_key: ""              # Tavily API key (for tavily engine)
  brave_api_key: ""               # Brave Search API key (for brave engine)
  serpapi_api_key: ""             # SerpAPI key (for serpapi engine)

mcp:
  enabled: true
  path: "/mcp"
  allowed_hosts:
    - "localhost"
    - "localhost:*"
    - "127.0.0.1"
    - "127.0.0.1:*"
  allowed_origins: []

tokens:
  - token: "sk-admin-key"
    name: "admin"
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `config.yaml` | Path to config file |
| `LIGHTPANDA_BIN` | `lightpanda` | Lightpanda binary path |
| `LIGHTPANDA_FETCH_TIMEOUT` | `30` | Fetch timeout in seconds |
| `LIGHTPANDA_MAX_CONCURRENT` | `5` | Max concurrent fetch requests |
| `LIGHTPANDA_TOKENS` | - | Comma-separated API tokens |
| `SEARCH_DEFAULT_ENGINE` | `duckduckgo` | Default search engine |
| `SEARCH_DEFAULT_FORMAT` | `json` | Default response format |
| `SEARCH_DEFAULT_NUM_RESULTS` | `5` | Default result count |
| `SEARCH_TIMEOUT` | `20` | Search provider timeout in seconds |
| `SEARCH_MAX_CONCURRENT` | `10` | Maximum concurrent searches |
| `TAVILY_API_KEY` | - | Tavily API key |
| `BRAVE_API_KEY` | - | Brave Search API key |
| `SERPAPI_API_KEY` | - | SerpAPI key |
| `MCP_MOUNT` | `false` | Mount MCP into the REST application |
| `MCP_ALLOWED_HOSTS` | localhost hosts | Comma-separated MCP Host allowlist |
| `MCP_CORS_ORIGINS` | - | Comma-separated browser Origin allowlist |

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
  -H "Authorization: Bearer sk-admin-key"

# HTML
curl "http://localhost:8010/fetch?url=https://example.com&return_type=html" \
  -H "Authorization: Bearer sk-admin-key"
```

### `GET /search`

Search the web via one of the supported search engines.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `q` | _(required)_ | Search query |
| `engine` | `duckduckgo` | Search engine: `duckduckgo`, `tavily`, `brave`, `serpapi` |
| `num_results` | `5` | Number of results (1-50) |
| `format` | `json` | Response format: `json` or `csv` |

**Authentication:** `Authorization: Bearer <token>` header (same as `/fetch`).

```bash
# DuckDuckGo (free, no API key)
curl "http://localhost:8010/search?q=python+programming&engine=duckduckgo" \
  -H "Authorization: Bearer sk-admin-key"

# Tavily (requires API key in config)
curl "http://localhost:8010/search?q=latest+AI+news&engine=tavily&num_results=5" \
  -H "Authorization: Bearer sk-admin-key"

# CSV output
curl "http://localhost:8010/search?q=test&format=csv" \
  -H "Authorization: Bearer sk-admin-key"

# Brave Search
curl "http://localhost:8010/search?q=climate+change&engine=brave&num_results=10" \
  -H "Authorization: Bearer sk-admin-key"

# SerpAPI
curl "http://localhost:8010/search?q=stock+market&engine=serpapi&num_results=5" \
  -H "Authorization: Bearer sk-admin-key"
```

#### Response format (JSON)

```json
{
  "success": true,
  "query": "python programming",
  "engine": "duckduckgo",
  "num_results": 5,
  "format": "json",
  "results": [
    {
      "title": "Python Tutorial",
      "url": "https://example.com/python",
      "snippet": "Learn Python programming..."
    }
  ]
}
```

### Search Providers

| Engine | Provider | API Key | Description |
|--------|----------|---------|-------------|
| `duckduckgo` | DuckDuckGo | **None** | Free web search via ddgs. No API key needed. |
| `tavily` | Tavily | Required | AI-optimized search. Install: `pip install agent-web-capability[tavily]` |
| `brave` | Brave Search | Required | Privacy-first search index. Install: `pip install agent-web-capability[brave]` |
| `serpapi` | SerpAPI | Required | Multi-engine search (Google, Bing, etc.). Install: `pip install agent-web-capability[serpapi]` |

### `GET /health`

```bash
curl http://localhost:8010/health
```

## MCP Integration

The service exposes both fetch and search as MCP tools for Claude Desktop and other MCP clients.

### Streamable HTTP mode (built into the REST server)

Set `MCP_MOUNT=1` and the MCP endpoint is available at `/mcp` alongside the REST API.

For a public hostname, add that hostname to `mcp.allowed_hosts`. DNS rebinding
protection remains enabled on non-local interfaces. Browser cross-origin access
is disabled unless `mcp.allowed_origins` is configured.

### Standalone MCP server

```bash
# Stdio mode (for Claude Desktop config)
awc mcp-serve

# HTTP mode
awc mcp-serve-http --host 0.0.0.0 --port 8011
```

## Docker

```bash
docker compose up -d
```

The container runs `awc serve`, picking up `config.yaml` from the mounted volume.
`config.yaml` is excluded from the image build context, so credentials are not
stored in image layers.

## Security

Fetches block private and internal networks by default, including redirects and
subresources resolved by Lightpanda. Disable `fetch.block_private_networks` only
for a deliberately isolated internal deployment. If no tokens are configured,
the API remains anonymous; public deployments should configure tokens and enforce
request-rate limits at the ingress or reverse proxy.

## Install Options

```bash
pip install .                              # Base: fetch + DuckDuckGo search
pip install ".[tavily]"                    # + Tavily provider
pip install ".[brave]"                     # + Brave Search provider
pip install ".[serpapi]"                   # + SerpAPI provider
pip install ".[all]"                       # All providers
```
