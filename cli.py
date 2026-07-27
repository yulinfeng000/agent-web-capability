import argparse
import secrets
import string

from config import AppConfig, DEFAULT_CONFIG_PATH, load_config


def serve(args):
    import uvicorn

    config = load_config(args.config)
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
    )


def gen_token(args):
    chars = string.ascii_letters + string.digits
    rand = "".join(secrets.choice(chars) for _ in range(32))
    token = f"sk-{rand}"
    entry = f'- token: "{token}"\n  name: "{args.name}"'
    print(entry)


def mcp_serve(args):
    """Run the MCP server in stdio mode (for Claude Desktop etc.)."""
    import anyio

    from mcp_server import create_mcp_server
    from browser import BrowserPool

    config = load_config(args.config)
    pool = BrowserPool(config)
    mcp = create_mcp_server(config, pool)

    print(f"Starting MCP server (stdio mode)...", flush=True, file=__import__("sys").stderr)
    anyio.run(mcp.run_stdio_async)


def mcp_serve_http(args):
    """Run the MCP server in Streamable HTTP mode (with optional Bearer token auth)."""
    import uvicorn

    from mcp_server import create_mcp_server
    from browser import BrowserPool
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.fastmcp.server import StreamableHTTPASGIApp
    from mcp.server.transport_security import TransportSecuritySettings
    from auth import MCPAuthMiddleware

    config = load_config(args.config)
    pool = BrowserPool(config)
    mcp = create_mcp_server(config, pool)

    host = args.host or config.server.host
    port = args.port or (config.server.port + 1)

    # Adjust transport security for the actual bind host.
    # FastMCP auto-configures allowed_hosts only for localhost; for other
    # hosts (e.g. 0.0.0.0) DNS rebinding protection needs to be disabled
    # since we can't predict valid Host header values.
    if host not in ("127.0.0.1", "localhost", "::1"):
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

    # Build ASGI app with auth (same pattern as MCP_MOUNT in main.py)
    session_manager = StreamableHTTPSessionManager(
        app=mcp._mcp_server,
        event_store=mcp._event_store,
        retry_interval=mcp._retry_interval,
        json_response=True,
        stateless=True,
        security_settings=mcp.settings.transport_security,
    )
    token_list = [t.token for t in config.tokens]

    asgi_app = MCPAuthMiddleware(
        StreamableHTTPASGIApp(session_manager),
        tokens=token_list,
    )

    print(f"Starting MCP server (HTTP mode) on {host}:{port}...", flush=True)
    uvicorn.run(asgi_app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(prog="awc", description="agent-web-capability CLI")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="Start the web fetch REST server")
    serve_parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})"
    )
    serve_parser.set_defaults(func=serve)

    mcp_parser = sub.add_parser("mcp-serve", help="Start the MCP server (stdio mode, for Claude Desktop)")
    mcp_parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})"
    )
    mcp_parser.set_defaults(func=mcp_serve)

    mcp_http_parser = sub.add_parser("mcp-serve-http", help="Start the MCP server (Streamable HTTP mode)")
    mcp_http_parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})"
    )
    mcp_http_parser.add_argument(
        "--host", default=None, help="Host to bind (default: from config)"
    )
    mcp_http_parser.add_argument(
        "--port", type=int, default=None, help="Port to bind (default: server.port + 1)"
    )
    mcp_http_parser.set_defaults(func=mcp_serve_http)

    token_parser = sub.add_parser("gen-token", help="Generate a random API token")
    token_parser.add_argument("name", nargs="?", default="", help="Token name (optional)")
    token_parser.set_defaults(func=gen_token)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
