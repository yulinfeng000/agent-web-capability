# agent-web-capability

A web capability service for AI agents — fetch and search the web. Powered by Lightpanda headless browser for fetching, with multiple search providers for finding current information.

## Available Tools

### web_fetch

Fetches a web page and returns its rendered content. The browser executes JavaScript and waits for the page to fully render before returning the content.

**Parameters:**

- `url` (required) — The URL to fetch. Must start with `http://` or `https://`.
- `return_type` (optional, default: `markdown`) — Output format:
  - `markdown` — Clean, LLM-friendly markdown (best for reading and analysis)
  - `html` — Raw rendered HTML
  - `plain_text` — Markdown converted to plain text (strips formatting)

**Usage tips:**

- Use `markdown` (the default) for most cases — it's optimized for LLM consumption with clean formatting.
- Use `html` when you need the full DOM structure, e.g., for scraping specific elements.
- Use `plain_text` when you only want the raw text content without any formatting.
- The browser waits for JavaScript to execute before capturing the page, so SPAs and JS-heavy sites work.
- If a page returns an error, the tool will return the error message — check the response carefully.

**Example:**

```
web_fetch(url="https://example.com", return_type="markdown")
```

### web_search

Search the web using a configurable search engine. Returns results as a JSON string with `query`, `engine`, and a `results` array — each result has `title`, `url`, and `snippet`.

**Parameters:**

- `query` (required) — The search query string. Be specific and include relevant keywords for better results.
- `engine` (optional, default: `duckduckgo`) — Which search backend to use:
  - `duckduckgo` — Free, no API key needed. Uses DuckDuckGo's web index via HTML scraping.
  - `tavily` — AI-optimized search API. Returns higher-quality, LLM-friendly results. Requires `tavily_api_key` in config.
  - `brave` — Privacy-first search with an independent index. Requires `brave_api_key` in config.
  - `serpapi` — Multi-engine API supporting Google, Bing, etc. Requires `serpapi_api_key` in config.
- `num_results` (optional, default: 5, range: 1-50) — Maximum number of results to return. Higher values may take longer.

**Response format:**

```json
{
  "query": "your search query",
  "engine": "duckduckgo",
  "results": [
    {
      "title": "Result title",
      "url": "https://example.com/page",
      "snippet": "A text snippet from the result..."
    }
  ]
}
```

**Usage tips:**

- Use `duckduckgo` for most cases — it's free and requires no configuration, making it the most reliable default.
- Use `tavily` when you need AI-optimized search results with better relevance and cleaner content extraction (requires API key).
- Use `brave` when you need privacy-respecting results from an independent search index (requires API key).
- Use `serpapi` when you need Google-quality results or access to non-web search engines like Google Scholar, Images, or News (requires API key).
- If a search fails with a provider requiring an API key, fall back to `duckduckgo`.
- The search results include only titles, URLs, and snippets — use `web_fetch` to retrieve full page content when you need more detail from a result.
- Keep queries concise but descriptive. Avoid overly long or vague queries.

**Error handling:**

- If the search engine returns an error (e.g., rate limiting, API key missing, service unavailable), the tool returns an error string rather than results. Check the response carefully.
- DuckDuckGo may be rate-limited if too many requests are made in quick succession — space out requests if needed.

**Example:**

```
web_search(query="latest developments in AI", engine="duckduckgo", num_results=5)
```
