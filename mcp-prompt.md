# lightpanda-webfetch

A web page fetching service powered by the Lightpanda headless browser. Use the `fetch` tool to retrieve and render web page content.

## Available Tools

### fetch

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
fetch(url="https://example.com", return_type="markdown")
```
