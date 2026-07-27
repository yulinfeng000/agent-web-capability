import argparse
import secrets
import string

import yaml

from .auth import TokenAuthenticator
from .browser import BrowserPool
from .config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from .service import WebCapabilityService


def _build_service(config: AppConfig) -> WebCapabilityService:
    return WebCapabilityService(config, BrowserPool(config))


def serve(args) -> None:
    import uvicorn

    from .app import create_app

    config = load_config(args.config)
    uvicorn.run(create_app(config), host=config.server.host, port=config.server.port)


def gen_token(args) -> None:
    chars = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(32))
    print(yaml.safe_dump([{"token": f"sk-{random_part}", "name": args.name}], sort_keys=False).rstrip())


def mcp_serve(args) -> None:
    import anyio

    from .mcp_server import create_mcp_server

    config = load_config(args.config)
    mcp = create_mcp_server(config, _build_service(config))
    anyio.run(mcp.run_stdio_async)


def mcp_serve_http(args) -> None:
    import uvicorn

    from .mcp_server import create_mcp_http_app

    config = load_config(args.config)
    host = args.host or config.server.host
    port = args.port or (config.server.port + 1)
    _, _, asgi_app = create_mcp_http_app(
        config,
        _build_service(config),
        TokenAuthenticator(config.tokens),
    )
    uvicorn.run(asgi_app, host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="awc", description="agent-web-capability CLI")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the REST and optional MCP server")
    serve_parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH)
    serve_parser.set_defaults(func=serve)

    mcp_parser = subparsers.add_parser("mcp-serve", help="Start the MCP server over stdio")
    mcp_parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH)
    mcp_parser.set_defaults(func=mcp_serve)

    mcp_http_parser = subparsers.add_parser(
        "mcp-serve-http", help="Start the MCP Streamable HTTP server"
    )
    mcp_http_parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH)
    mcp_http_parser.add_argument("--host", default=None)
    mcp_http_parser.add_argument("--port", type=int, default=None)
    mcp_http_parser.set_defaults(func=mcp_serve_http)

    token_parser = subparsers.add_parser("gen-token", help="Generate a random API token")
    token_parser.add_argument("name", nargs="?", default="")
    token_parser.set_defaults(func=gen_token)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
