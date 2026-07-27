from argparse import Namespace

import uvicorn

from agent_web_capability.cli import serve


def test_serve_passes_loaded_config_to_application(monkeypatch, tmp_path):
    config_path = tmp_path / "custom.yml"
    config_path.write_text(
        """
server:
  host: 127.0.0.2
  port: 9123
tokens:
  - token: custom-secret
    name: custom
""".strip(),
        encoding="utf-8",
    )
    captured = {}

    def run(app, host, port):
        captured.update(app=app, host=host, port=port)

    monkeypatch.setattr(uvicorn, "run", run)
    serve(Namespace(config=str(config_path)))

    assert captured["host"] == "127.0.0.2"
    assert captured["port"] == 9123
    assert captured["app"].state.config.tokens[0].token == "custom-secret"
