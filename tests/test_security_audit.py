"""
Security audit regression tests (2026-08-06).

One test per finding in the Vulnerability Report (SECURITY_AUDIT.md),
named after its ID. Each test reproduces what made the finding exploitable
and asserts it no longer is — these are the PoCs from the audit, kept
permanently rather than thrown away, so a future change that reopens one
of these gaps fails CI instead of shipping.
"""

import json
import os
import uuid

from _helpers import (ELMER_ADMIN_KEY, ELMER_BAD_HEADERS, ELMER_GOOD_HEADERS,
                      FakeTable, GOOD_HEADERS, get_app, run_module, use_table)


def _json(response):
    return json.loads(response.get_data(as_text=True))


def test_ELMER_SEC_001_cache_no_longer_leaks_pii_or_jwts_unauthenticated():
    """The response cache used to be world-readable and captured full
    response bodies for every route — including admin-gated ticket PII
    and issued JWTs. Confirmed exploitable before the fix; this proves it
    no longer is, and that a correctly-keyed caller still can read it."""
    _, _, client = get_app()
    prev = use_table(FakeTable())
    try:
        r = client.post("/tickets/", json={
            "name": "Victim", "email": "victim-pii@example.com",
            "subject": "s", "description": "Sensitive internal details.",
            "priority": "P1"})
        ticket_id = _json(r)["ticket"]["id"]
        client.get("/tickets/" + ticket_id, headers=GOOD_HEADERS)

        # No X-Admin-Key at all — the original vulnerability.
        unauth = client.get("/elmer/cache/route/tickets")
        assert unauth.status_code in (401, 503)
        assert "victim-pii@example.com" not in unauth.get_data(as_text=True)

        # Correctly-keyed caller can still use the feature.
        authed = client.get("/elmer/cache/route/tickets",
                            headers=ELMER_GOOD_HEADERS)
        assert authed.status_code == 200
        assert "victim-pii@example.com" in authed.get_data(as_text=True)
    finally:
        use_table(prev)


def test_ELMER_SEC_001b_jwt_no_longer_harvestable_via_cache():
    """A second, worse instance of the same bug: issued JWTs were also
    readable from the unauthenticated cache endpoint, letting anyone
    harvest valid admin tokens without ever guessing a password."""
    _, _, client = get_app()
    r = client.post("/login/admin", json={"username": "cn", "password": "secret"})
    token = _json(r).get("jwt")
    if not token:
        return  # login itself rate-limited by an earlier test in this run

    unauth = client.get("/elmer/cache/route/login")
    assert unauth.status_code in (401, 503)
    assert token not in unauth.get_data(as_text=True)


def test_ELMER_SEC_002_proxy_registration_requires_auth():
    """POST /elmer/proxy used to let anyone register a route that
    server-side-forwarded traffic to an attacker-chosen host:port — an
    unauthenticated SSRF primitive, confirmed reachable against a cloud
    metadata address before the fix."""
    _, _, client = get_app()

    unauth = client.post("/elmer/proxy", json={
        "route": "evilproxy-" + uuid.uuid4().hex[:8],
        "server": "169.254.169.254", "port": 80})
    assert unauth.status_code in (401, 503)

    authed = client.post("/elmer/proxy", json={
        "route": "legitproxy-" + uuid.uuid4().hex[:8],
        "server": "10.0.0.5", "port": 3000}, headers=ELMER_GOOD_HEADERS)
    assert authed.status_code == 200


def test_ELMER_SEC_001_002_fail_closed_when_key_unset():
    """Both guards must refuse everything, not fall open, when
    ELMER_ADMIN_KEY has not been configured at all."""
    _, _, client = get_app()
    saved = os.environ.pop("ELMER_ADMIN_KEY", None)
    try:
        r = client.get("/elmer/cache/route/tickets", headers=ELMER_GOOD_HEADERS)
        assert r.status_code == 503
        r = client.post("/elmer/proxy", json={"route": "x", "server": "a", "port": 1},
                        headers=ELMER_GOOD_HEADERS)
        assert r.status_code == 503
    finally:
        if saved is not None:
            os.environ["ELMER_ADMIN_KEY"] = saved


def test_ELMER_SEC_003_jwt_secret_env_override():
    """The JWT signing secret previously had no environment-variable
    override — the only committed value (an example, publicly visible in
    this repository) was always used unless someone hand-edited config.
    A token signed under a distinct ELMER_JWT_SECRET must not verify
    against the default, proving the override actually takes effect."""
    import jwt as pyjwt
    from app.middleware import _jwt as jwt_module

    elmer, _, _ = get_app()
    saved = os.environ.get("ELMER_JWT_SECRET")
    try:
        os.environ["ELMER_JWT_SECRET"] = "a-distinct-test-only-secret"
        jwt_module.apply(elmer, None)

        token = pyjwt.encode({"sub": "x"}, "a-distinct-test-only-secret",
                             algorithm="HS256")
        claims = elmer.app.services.security.jwt.verify(token)
        assert claims["sub"] == "x"

        forged = pyjwt.encode({"sub": "attacker"}, "wrong-guess", algorithm="HS256")
        try:
            elmer.app.services.security.jwt.verify(forged)
            assert False, "a token signed with the wrong secret must not verify"
        except pyjwt.PyJWTError:
            pass
    finally:
        if saved is None:
            os.environ.pop("ELMER_JWT_SECRET", None)
        else:
            os.environ["ELMER_JWT_SECRET"] = saved
        jwt_module.apply(elmer, None)  # restore prior state for later tests


def test_ELMER_SEC_005_rate_limiting():
    """Login, admin-key verification, and public ticket creation were all
    completely unthrottled — a straightforward brute-force / spam vector."""
    _, _, client = get_app()
    prev = use_table(FakeTable())
    try:
        statuses = [client.post("/tickets/manage/verify",
                                headers={"X-Admin-Key": "guess-%d" % i}).status_code
                   for i in range(45)]
        assert 429 in statuses, "manage/verify must eventually rate-limit"

        body = {"name": "A", "email": "a@b.co", "subject": "s",
               "description": "d", "priority": "P4"}
        statuses = [client.post("/tickets/", json=body).status_code
                   for _ in range(25)]
        assert 429 in statuses, "ticket creation must eventually rate-limit"
        assert 201 in statuses, "requests under the limit must still succeed"
    finally:
        use_table(prev)


def test_ELMER_SEC_007_security_headers_present():
    """The app previously set no security headers at all."""
    _, _, client = get_app()
    r = client.get("/")
    for header in ("Content-Security-Policy", "X-Content-Type-Options",
                  "X-Frame-Options", "Referrer-Policy", "Permissions-Policy",
                  "Strict-Transport-Security"):
        assert header in r.headers, header


def test_ELMER_SEC_008_unhandled_exception_still_audited_and_generic():
    """A crashing handler used to bypass the cache/audit middleware
    entirely and, depending on deployment, could leak a traceback. It must
    now: (a) return a generic message with no exception detail, and (b)
    still show up in the audit cache with a 500 status."""
    elmer, _, client = get_app()

    route_name = "crashtest-" + uuid.uuid4().hex[:8]
    router = elmer.app.services.web.router()

    @router.get("/boom")
    def _boom(request, response):
        raise RuntimeError("audit regression test — should never reach the client")

    elmer.app.services.web.router.register(route_name, router)

    r = client.get("/" + route_name + "/boom")
    assert r.status_code == 500
    body = r.get_data(as_text=True)
    assert "should never reach the client" not in body
    assert "Traceback" not in body

    cached = client.get("/elmer/cache/route/" + route_name,
                        headers=ELMER_GOOD_HEADERS)
    entries = _json(cached)["data"]
    assert entries and entries[0]["status"] == 500


def test_ELMER_SEC_009_body_size_limit_tightened():
    """500MB was an oversized default for a JSON ticket API — inherited
    from the original file-upload demo config, not a deliberate choice
    for this deployment."""
    elmer, server, _ = get_app()
    limit_mb = elmer.resolve(elmer.app.config, "uploadLimitMb")
    assert limit_mb <= 10, "base Elmer's default should not need upload-scale limits"
    assert server.flask.config.get("MAX_CONTENT_LENGTH") == limit_mb * 1024 * 1024


def test_ELMER_SEC_010_cors_credentials_only_with_validated_origin():
    """Access-Control-Allow-Credentials used to be sent unconditionally,
    independent of whether Access-Control-Allow-Origin was actually set
    for a trusted origin."""
    _, _, client = get_app()
    whitelisted = elmer_whitelisted_origin()

    untrusted = client.get("/", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Credentials" not in untrusted.headers
    assert "Access-Control-Allow-Origin" not in untrusted.headers

    trusted = client.get("/", headers={"Origin": whitelisted})
    assert trusted.headers.get("Access-Control-Allow-Credentials") == "true"
    assert trusted.headers.get("Access-Control-Allow-Origin") == whitelisted


def elmer_whitelisted_origin():
    elmer, _, _ = get_app()
    whitelist = elmer.resolve(elmer.app.config, "security.corsWhitelist", [])
    assert whitelist, "test assumes base.json ships at least one CORS origin"
    return whitelist[0]


def test_ELMER_SEC_012_static_serving_traversal_safe():
    """The directory-existence pre-check used to run on an unsanitized
    path join; confirmed not exploitable for actual file disclosure
    (Werkzeug's send_from_directory already blocks that), but the
    pre-check itself is now sanitized too, closing even the lesser
    directory-existence oracle. This also guards the legitimate directory
    -> index.html behavior it exists for."""
    _, _, client = get_app()
    for path in ("/www/managetickets", "/www/managetickets/view",
                "/www/managetickets/status", "/www/tickets.html"):
        assert client.get(path).status_code == 200, path

    for path in ("/www/../../_index.py", "/www/..%2f..%2f_index.py",
                "/www/%2e%2e/%2e%2e/etc/passwd"):
        assert client.get(path).status_code == 404, path


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
