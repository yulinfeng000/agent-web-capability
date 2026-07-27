# agent-web-capability

A web capability service for AI agents. Use `web_search` to find current
information and `web_fetch` to retrieve the rendered contents of a URL.

## Tools

### web_fetch

- `url`: An absolute HTTP or HTTPS URL.
- `return_type`: `markdown`, `html`, or `plain_text`.

Private and internal network destinations are blocked by default. A tool error
means the page could not be fetched; do not treat the error text as page content.

### web_search

- `query`: A non-empty search query.
- `engine`: `duckduckgo`, `tavily`, `brave`, or `serpapi`.
- `num_results`: An integer from 1 through 50.

The result is structured data containing `query`, `engine`, and a `results`
array. Each result contains `title`, `url`, and `snippet`.
