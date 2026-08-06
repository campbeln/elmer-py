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


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
