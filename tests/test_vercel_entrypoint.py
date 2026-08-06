"""The Vercel entrypoint must expose a working WSGI app without listening."""

import importlib.util
import json
import os
import sys

from _helpers import ROOT, run_module


def _load_entrypoint():
    # Import api/index.py exactly the way Vercel's runtime would.
    sys.argv = ["index.py", "dev"]
    path = os.path.join(ROOT, "api", "index.py")
    spec = importlib.util.spec_from_file_location("vercel_entry_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exposes_flask_app_and_serves_routes():
    module = _load_entrypoint()
    app = module.app
    assert type(app).__name__ == "Flask"

    client = app.test_client()
    heartbeat = json.loads(client.get("/").get_data(as_text=True))
    assert heartbeat["ok"] is True

    meta = json.loads(
        client.get("/tickets/meta/priorities").get_data(as_text=True))
    assert len(meta["priorities"]) == 4

    assert client.get("/www/tickets.html").status_code == 200


def test_vercel_json_has_no_legacy_builds():
    """`builds` in vercel.json makes Vercel ignore all dashboard Build &
    Development Settings and emits a deploy-time warning. Zero-config
    detection of api/index.py replaces it — this guards against it
    creeping back."""
    with open(os.path.join(ROOT, "vercel.json"), encoding="utf8") as handle:
        config = json.load(handle)
    assert "builds" not in config


def test_vercel_json_routes_everything_to_the_function():
    """The catch-all must use `routes`, NOT `rewrites`: rewrites apply
    after Vercel's filesystem check, which in a no-framework project would
    serve repo files — including app/config/*.json with its secrets — as
    static assets. `routes` (with no `handle: filesystem` entry) sends
    every request to the function before any static serving."""
    with open(os.path.join(ROOT, "vercel.json"), encoding="utf8") as handle:
        config = json.load(handle)
    assert "rewrites" not in config, "rewrites would expose repo files statically"
    routes = config.get("routes", [])
    assert routes and routes[0]["src"] == "/(.*)"
    assert routes[0]["dest"].startswith("/api/index")
    assert not any("handle" in r for r in routes)


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
