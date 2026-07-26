import argparse
import secrets
import string

from config import load_config


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
    token = f"sk-lightpanda-{rand}"
    entry = f'- token: "{token}"\n  name: "{args.name}"'
    print(entry)


def main():
    parser = argparse.ArgumentParser(prog="lpwf", description="lightpanda-webfetch CLI")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="Start the web fetch server")
    serve_parser.add_argument(
        "-c", "--config", default="config.yaml", help="Path to config file (default: config.yaml)"
    )
    serve_parser.set_defaults(func=serve)

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
