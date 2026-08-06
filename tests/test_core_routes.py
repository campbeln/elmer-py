"""Core Elmer routes: heartbeat, JWT login, response tracking, cache, statics."""

import json

from _helpers import get_app, run_module


def _json(response):
    return json.loads(response.get_data(as_text=True))


def test_heartbeat():
    _, _, client = get_app()
    response = client.get("/")
    data = _json(response)
    assert response.status_code == 200
    assert data["ok"] is True
    assert "versions" in data


def test_jwt_login_good_and_bad():
    _, _, client = get_app()
    good = client.post("/login/admin",
                       json={"username": "cn", "password": "secret"})
    assert good.status_code == 200
    token = _json(good)["jwt"]
    assert token and "p" not in _json(good)   # password never echoed back

    bad = client.post("/login/admin",
                      json={"username": "cn", "password": "wrong"})
    assert bad.status_code == 401

    verify = client.post("/login/verify/admin", json={"jwt": token})
    assert verify.status_code == 200
    assert _json(verify)["username"] == "cn"


def test_response_tracking_lifecycle():
    _, _, client = get_app()
    created = client.post("/elmer/response", json={"data": {"a": 1}})
    assert created.status_code == 200
    response_id = _json(created)["id"]

    updated = client.post("/elmer/response/" + response_id,
                          json={"data": {"a": 2}, "done": True})
    assert updated.status_code == 200
    assert _json(updated)["done"] != ""

    read = client.get("/elmer/response/" + response_id)
    assert read.status_code == 200

    missing = client.get("/elmer/response/no-such-id")
    assert missing.status_code == 404


def test_proxy_registration_disallows_reserved_routes():
    _, _, client = get_app()
    rejected = client.post("/elmer/proxy", json={
        "route": "login", "port": 3000, "server": "10.0.0.5"})
    assert rejected.status_code == 409


def test_request_id_tracing_and_cache():
    _, _, client = get_app()

    # A generated trace id is attached and honoured end to end.
    response = client.get("/")
    assert "X-Request-Id" in response.headers
    trace = json.loads(response.headers["X-Request-Id"])
    assert trace["id"], "generated trace id must not be blank"

    # An inbound id wins over generation.
    echoed = client.get("/", headers={"X-Request-Id": "abc-123"})
    assert json.loads(echoed.headers["X-Request-Id"])["id"] == "abc-123"

    # The cache middleware stored the response under the trace id.
    cached = client.get("/elmer/cache/id/" + trace["id"])
    assert cached.status_code == 200

    cleared = client.get("/elmer/cache/clear/id/" + trace["id"])
    assert _json(cleared)["cleared"] is True


def test_static_pages_serve():
    _, _, client = get_app()
    for path in ("/www/index.html", "/www/tickets.html",
                 "/www/managetickets", "/www/managetickets/view",
                 "/www/managetickets/status",
                 "/www/managetickets/shared.css",
                 "/www/managetickets/shared.jsx"):
        assert client.get(path).status_code == 200, path


def test_static_directory_serves_index():
    _, _, client = get_app()
    body = client.get("/www/managetickets/status").get_data(as_text=True)
    assert "<title>Update status" in body


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
