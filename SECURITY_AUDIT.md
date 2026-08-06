# Security Audit — Elmer-Py

**Date:** 2026-08-06
**Scope:** Full `elmer-py` codebase — application code, configuration,
dependencies, and the deployed `/tickets` + management-console feature set.
**Method:** Static review (secrets/pattern search, dependency audit) plus
dynamic verification — every finding below was reproduced against a
running instance before being fixed, and re-verified after.

## Summary

| Severity | Count | Fixed |
|---|---|---|
| Critical | 2 | 2 |
| High | 3 | 2 |
| Medium | 5 | 5 |
| Low | 2 | 1 |
| **Total** | **12** | **10** |

Both Critical findings were internet-exploitable in the deployed
configuration (`elmer-py-seven.vercel.app`) at the time of audit: an
unauthenticated cache endpoint that leaked admin-gated PII and issued
JWTs, and an unauthenticated SSRF primitive via child-API proxy
registration. Both are closed and verified. Two findings — a design
limitation and an accepted residual risk — are documented rather than
changed; see their entries for why.

---

## Phase 1 — Reconnaissance findings (non-OWASP-numbered)

| Check | Result |
|---|---|
| Dependency vulnerabilities (`pip-audit`, isolated venv from `requirements.txt`) | **Clean.** Flask 3.1.3, Flask-Compress 1.24, PyJWT 2.13.0, requests 2.34.2, Werkzeug 3.1.8 — zero known CVEs. (A bare `pip-audit` against this shared sandbox's global environment also flagged unrelated pre-installed tooling like `pypdf`/`pip` itself — not part of this project's dependency tree, excluded.) |
| Hardcoded secrets/passwords/API keys | **Found** — see ELMER-SEC-003, ELMER-SEC-004. |
| Hardcoded IPs/URLs | `dns1`/`dns2` = `1.1.1.1`/`1.0.0.1` (public Cloudflare resolvers, not sensitive). All other literal URLs are `localhost` (docs/examples) or documentation references (Stack Overflow, hilton.org.uk). No suspicious or exfiltration-looking endpoints. **Informational only, no action.** |
| SQL injection patterns | **N/A** — Elmer talks to Supabase exclusively via PostgREST/HTTP, never raw SQL. (See ELMER-SEC-004's note on filter-value construction for the adjacent risk that *does* apply to this architecture.) |
| `eval`/`exec` usage | **None found.** |
| `pickle`/`marshal`/unsafe deserialization | **None found.** |
| `dangerouslySetInnerHTML` / DOM XSS sinks in the `/www` React pages | **None found** — all rendering goes through JSX's default escaping. |
| Path traversal (static file serving) | **Blocked** — Werkzeug's `safe_join` rejects traversal in the actual file read. A secondary, non-exploitable directory-existence oracle in the pre-check was found and closed anyway; see ELMER-SEC-012. |
| Authentication inventory | JWT (HS256, PyJWT, `algorithms=` pinned — not vulnerable to `alg:none`/confusion attacks), HTTP Basic (timing-safe `hmac.compare_digest`), and a shared bearer token (`X-Admin-Key`) for the ticket-management and Elmer-operational surfaces. No MFA, no session cookies, no OAuth — consistent with this being a small internal-tool scaffold. |
| Authorization inventory | Coarse-grained only: JWT `role` claim (admin/internal/external) with no per-action RBAC; ticket management and Elmer's own operational endpoints each gate on one shared secret with no per-user identity. See ELMER-SEC-011. |
| Data protection | Supabase RLS enabled with no permissive policies (service-role key bypasses it by design — access control lives in the API layer). No field-level encryption at rest; TLS in transit depends on the deployment platform (Vercel terminates it; the Docker path has no TLS of its own — expected for a service meant to sit behind a reverse proxy or platform load balancer). |
| Infrastructure | HTTPS: platform-dependent (see above). Security headers: were entirely absent — fixed (ELMER-SEC-007). Rate limiting: was entirely absent — fixed (ELMER-SEC-005). |

---

## Vulnerability Report

### ELMER-SEC-001 — Unauthenticated cache endpoint exposes all admin-gated data and issued JWTs

- **Severity:** Critical — respond immediately
- **Category:** A01 Broken Access Control / A09 Logging failures (sensitive data retained and exposed) / de facto A07 (enables full auth bypass via token theft)
- **Status:** ✅ Fixed
- **Description:** `_cache.py` middleware stores the full response body of every request through every registered route into `elmer.app.cache`, keyed by trace ID and tagged by route name. The `/elmer/cache/*` read endpoints that expose this store had no authentication at all — meaning anyone could read the complete history of responses from *every other route in the app*, including ones that were themselves properly access-controlled.
- **Location:** `app/routes/elmer.py` (all `/cache/*` handlers), `app/middleware/_cache.py`
- **Impact:** Total bypass of every other access control in the application. Confirmed two concrete exploitation paths: (1) `GET /elmer/cache/route/tickets` with no auth returned reporter names, emails, and full ticket descriptions that were only ever supposed to be visible with a valid `X-Admin-Key`; (2) `GET /elmer/cache/route/login` with no auth returned complete, valid JWTs issued to anyone who had recently logged in — letting an attacker harvest working admin/internal/external tokens without ever guessing a password.
- **Proof of Concept (pre-fix, reproduced against a running instance):**
  ```python
  client.post("/tickets/", json={"email": "victim@example.com", ...})
  client.get("/tickets/<id>", headers={"X-Admin-Key": "correct-key"})  # legitimate admin read
  r = client.get("/elmer/cache/route/tickets")  # NO auth header at all
  assert "victim@example.com" in r.get_data(as_text=True)  # True — leaked

  client.post("/login/admin", json={"username": "cn", "password": "secret"})
  r = client.get("/elmer/cache/route/login")  # NO auth header
  assert issued_jwt in r.get_data(as_text=True)  # True — token harvested
  ```
- **Recommendation / Fix applied:** Added a dedicated, fail-closed `X-Admin-Key` guard (`ELMER_ADMIN_KEY` env var, `hmac.compare_digest` comparison) to every `/elmer/cache/*` route, deliberately using a separate secret from `TICKETS_ADMIN_KEY` since these are different privilege domains. Regression test: `tests/test_security_audit.py::test_ELMER_SEC_001_*`.

### ELMER-SEC-002 — Unauthenticated SSRF via child-API proxy registration

- **Severity:** Critical — respond immediately
- **Category:** A10 SSRF / A01 Broken Access Control (missing authorization on a privileged action)
- **Status:** ✅ Fixed
- **Description:** `POST /elmer/proxy` let any caller register a route name that would server-side-forward all matching traffic to an attacker-supplied `server`/`port`, with zero authentication, zero allowlisting, and zero validation of the target (no blocking of private/link-local ranges or the cloud metadata address).
- **Location:** `app/routes/elmer.py` (`_proxy` handler), `app/app_ex.py` (`_make_proxy_router`, the actual forwarding logic)
- **Impact:** A remote, unauthenticated attacker could make the Elmer server issue arbitrary HTTP requests to any host reachable from it — including, on most cloud platforms, the instance metadata service (`169.254.169.254`), which frequently yields IAM/service credentials. The response was reflected straight back to the attacker, making this a full SSRF-with-response oracle, not just a blind one.
- **Proof of Concept (pre-fix, reproduced):**
  ```python
  r = client.post("/elmer/proxy", json={
      "route": "evilproxy", "server": "169.254.169.254", "port": 80})
  assert r.status_code == 200  # accepted with no auth
  # Any subsequent request to /evilproxy/* is now forwarded server-side
  # to http://169.254.169.254:80/*
  ```
- **Recommendation / Fix applied:** Same `ELMER_ADMIN_KEY` guard as ELMER-SEC-001, applied to `POST /elmer/proxy`. **Breaking change, documented:** any legitimate child-API self-registration must now send the header. Full SSRF-grade hardening (target allowlisting, blocking RFC1918/link-local ranges) is a reasonable follow-up but out of scope for this pass — authentication was the missing control that mattered most, since the feature is explicitly designed to forward wherever it's told.

### ELMER-SEC-003 — JWT signing secret had no environment override; shipped example secret is public

- **Severity:** High — respond within 24–72 hours
- **Category:** A02 Cryptographic Failures / A05 Security Misconfiguration (default credentials)
- **Status:** ✅ Fixed
- **Description:** `app/config/base.json` ships a real-looking, cryptographically-random-looking JWT signing secret for local development to work out of the box. Unlike `SUPABASE_SERVICE_KEY`/`TICKETS_ADMIN_KEY`, this secret had no environment-variable override — the only way to change it was hand-editing the committed config file, which is easy to forget. Since this codebase is openly distributed, the shipped secret must be treated as public.
- **Location:** `app/config/base.json` (`security.jwt.salt.jwtSecret`), `app/middleware/_jwt.py`
- **Impact:** Any deployment that didn't think to edit the config file signs and verifies JWTs with a secret anyone auditing this source (or receiving this zip) already has — full authentication bypass, forge tokens for any role.
- **Recommendation / Fix applied:** Added `ELMER_JWT_SECRET` (and `ELMER_JWT_LOCAL_SECRET`) environment overrides, resolved *live* at every signing/verification call site — not just once at startup — so rotation takes effect without a restart. **Bug caught during verification:** the first implementation only threaded the override through `login()` and the route-guarding middleware, not the standalone `verify()` function used by `/login/verify/:mode` — meaning a token signed under a rotated secret could fail to verify through that one endpoint while succeeding everywhere else. Found via the regression test itself failing, fixed, re-verified. Also added a startup detector (SHA-256 fingerprint comparison, never the plaintext) that prints a loud warning if the shipped example secret or any shipped example password is still in use.

### ELMER-SEC-004 — Credentials stored in plaintext in config

- **Severity:** High — respond within 24–72 hours
- **Category:** A02 Cryptographic Failures
- **Status:** ⚠️ Documented, not changed — see rationale
- **Description:** Basic-auth and JWT user passwords live as plaintext strings in `app/config/base.json` (`"p": "pass1"`, `"p": "secret"`, etc.), not hashed. Comparison at request time is timing-safe (`hmac.compare_digest`), but storage is not — anyone with read access to the config (or a backup, or an env dump if it were env-sourced) sees real passwords directly.
- **Location:** `app/config/base.json` (`security.basic.users`, `security.jwt.{admin,internal,external}`)
- **Impact:** Config leakage (misconfigured backup, accidental commit of a locally-edited config, etc.) directly exposes usable credentials rather than hashes that would need cracking.
- **Recommendation (not applied this pass):** Hash stored passwords (bcrypt/argon2/scrypt via `passlib` or `werkzeug.security.generate_password_hash`) and compare hashes at request time. **Why not fixed now:** this is a real architecture change — the user-list format, the comparison logic in both `_basicauth.py` and `_jwt.py`'s `login()`, and the demo/example config all need to move together, and getting it wrong risks a worse bug (e.g., timing leaks in a hand-rolled hash comparison) shipped without adequate testing time. Flagged as the top follow-up item rather than rushed. The startup warning added for ELMER-SEC-003 already flags any shipped-example password still in use, which mitigates the most likely real-world instance of this risk (forgetting to rotate the demo credentials) even before the storage format changes.

### ELMER-SEC-005 — No rate limiting anywhere

- **Severity:** High — respond within 24–72 hours
- **Category:** A04 Insecure Design / A07 Authentication Failures
- **Status:** ✅ Fixed
- **Description:** Nothing in the codebase throttled repeated requests. `/login/*` (credential brute force), `/tickets/manage/verify` (admin-key brute force), and `POST /tickets` (unauthenticated-by-design spam/resource exhaustion) were all fully open to unlimited attempts. The existing per-request random delay in the auth middleware (0–99ms, derived from `time.monotonic()`) is not a meaningful mitigation — it doesn't limit *volume*, just adds negligible latency, and the code's own comment already flagged it as "security through obscurity."
- **Location:** (new) `app/middleware/_ratelimit.py`; applied in `app/middleware/_jwt.py` (`login_router`) and `app/routes/tickets.py` (`_create`, `_manage_verify`)
- **Impact:** Unlimited credential-guessing against login and the admin key; unlimited free-form ticket creation (storage/cost exhaustion, spam).
- **Proof of Concept (pre-fix, reproduced):** 15 wrong-password attempts against `/login/admin` and 20 against `/tickets/manage/verify` all returned `401` with no throttling.
- **Recommendation / Fix applied:** Fixed-window in-process rate limiter — 10/min on login, 20/5min on ticket creation, 15/5min on admin-key verification. **Bug caught during verification:** the first implementation used a relative import (`from ._ratelimit import check`) inside `tickets.py`, which is loaded via a flat dynamic module loader with no parent package (see `app/_app.py`'s `_load_module_from_path`) — relative imports there raise `ImportError` at request time, which the new exception-safety fix (ELMER-SEC-008) silently turned into a generic 500 instead of a crash, which is *how the bug was caught*: rate limiting appeared to do nothing in a first verification pass. Fixed with an absolute import; confirmed all three limits now trigger correctly. **Honestly documented limitation:** state is in-process memory. This holds reliably on the Docker/traditional deployment path; on Vercel it is best-effort only, since concurrent invocations may not share memory and any container recycle resets counters — the same constraint this project already documents for `elmer.app.cache` and the proxy registry.

### ELMER-SEC-006 — Docker "production" image ran Flask's development server

- **Severity:** Medium — respond within 1–2 weeks
- **Category:** A05 Security Misconfiguration
- **Status:** ✅ Fixed
- **Description:** `Dockerfile`'s `CMD` ran `python _index.py`, which called `flask.run(...)` — Werkzeug's own documentation states this server is not designed for production use (no real concurrency model, no hardening against slow-client / resource-exhaustion patterns).
- **Location:** `Dockerfile`, `app/_express.py` (`Server.listen`)
- **Impact:** Denial-of-service exposure disproportionate to load; not a data-exposure bug on its own, but a well-known anti-pattern a scanner or reviewer would immediately flag.
- **Recommendation / Fix applied:** `Server.listen()` now prefers `waitress` (pure-Python, cross-platform — works on Windows too, matching this project's own QUICKSTART, unlike gunicorn) when installed, falling back to the Flask dev server with an explicit stderr warning if it isn't. Added to `requirements.txt`/`pyproject.toml`. **Scoped correctly:** the Vercel deployment path never calls `.listen()` at all (confirmed via `api/index.py`), so this change only affects Docker/traditional hosting, and `waitress` was deliberately not added to `api/requirements.txt`.

### ELMER-SEC-007 — No security headers

- **Severity:** Medium — respond within 1–2 weeks
- **Category:** A05 Security Misconfiguration
- **Status:** ✅ Fixed
- **Description:** The application set zero security headers on any response — no CSP, no `X-Frame-Options`, no `X-Content-Type-Options`, no `Referrer-Policy`, no `Strict-Transport-Security`.
- **Location:** `_index.py` (`build()`)
- **Recommendation / Fix applied:** Added all five via an `after_request` hook. The CSP's `script-src`/`style-src` include `'unsafe-inline'` — a deliberate, documented trade-off: the `/www` pages are zero-build, with JSX transpiled client-side by Babel from inline `<script type="text/babel">` blocks, so there is no nonce/build pipeline to attach a stricter policy to. Everything else in the policy stays tight (named origins only, `object-src 'none'`, `frame-ancestors 'none'`).

### ELMER-SEC-008 — Unhandled exceptions bypassed the app's own audit/logging middleware

- **Severity:** Medium — respond within 1–2 weeks
- **Category:** A09 Logging and Monitoring Failures
- **Status:** ✅ Fixed
- **Description:** A route handler that raised an exception skipped straight past `response.emit_finish()` in `app/_express.py`'s request-dispatch code — meaning the cache/audit-log middleware (the only durable record this app keeps of what happened on a request) never fired. A crash triggered by malicious input left no trace beyond an ephemeral stderr traceback, easily lost in containers or serverless.
- **Location:** `app/_express.py` — both the static-blueprint dispatch path and the dynamic (runtime-registered proxy) dispatch path had the same gap, independently.
- **Recommendation / Fix applied:** Extracted a shared `_call_handler_safely()` helper used by both dispatch paths: catches the exception, logs it to stderr with the trace ID for correlation, returns a generic `500` (never the exception text — that would be its own A05 information-disclosure regression), and still calls `emit_finish()` so the crash shows up in the audit cache with an accurate status.

### ELMER-SEC-009 — Oversized default request-body limit on a JSON API

- **Severity:** Medium — respond within 1–2 weeks
- **Category:** A04 Insecure Design (resource exhaustion)
- **Status:** ✅ Fixed
- **Description:** `uploadLimitMb: 500` (500MB) applied globally via `MAX_CONTENT_LENGTH`, inherited from the original Node example's file-upload demo. The deployed base-Elmer + ticket API never handles file uploads at all, so an unauthenticated caller could force the server to buffer up to 500MB per request before any of `tickets.py`'s field-length validation ever ran.
- **Location:** `app/config/base.json`, `app/childapi/config/base.json`
- **Recommendation / Fix applied:** Lowered to 10MB (`base.json` — no upload use case) and 50MB (`childapi/config/base.json` — its demo route does showcase file upload, so some headroom is legitimate, but 500MB was still an oversized default to ship).

### ELMER-SEC-010 — `Access-Control-Allow-Credentials` set unconditionally

- **Severity:** Medium — respond within 1–2 weeks
- **Category:** A05 Security Misconfiguration
- **Status:** ✅ Fixed
- **Description:** The CORS middleware set `Access-Control-Allow-Credentials: true` on every response regardless of whether the request's `Origin` was actually on the whitelist (i.e., regardless of whether `Access-Control-Allow-Origin` was set at all).
- **Location:** `app/app_ex.py`
- **Impact:** Not independently exploitable — browsers still require a specific, matching `Access-Control-Allow-Origin` for a credentialed request to succeed, so an absent ACAO already blocks the response from being read by page JS regardless of ACAC. Flagged because it's exactly the kind of misconfiguration a scanner reports and a future edit could easily turn into a real bug (e.g., if `Allow-Origin` were ever changed to a wildcard alongside this).
- **Recommendation / Fix applied:** Now only set inside the `if origin and origin in whitelist:` branch.

### ELMER-SEC-011 — Shared single bearer secret for the whole management console; no per-user authorization or audit trail

- **Severity:** Low
- **Category:** A01 Broken Access Control (missing granular authorization)
- **Status:** ⚠️ Documented, not changed — architectural, and already disclosed
- **Description:** `TICKETS_ADMIN_KEY` and `ELMER_ADMIN_KEY` are both single shared secrets — anyone holding one can perform every action available under it, and there is no record of *which* holder did *what*.
- **Location:** `app/routes/tickets.py` (`_admin_guard`), `app/routes/elmer.py` (`_admin_guard`)
- **Recommendation:** For a real multi-operator deployment, move to the JWT login flow this project already ships (per-user identity, roles) rather than a shared bearer token, and add an audit-log entry per privileged action (who, what, when) distinct from the general response cache. Not changed this pass — this is a design-level change to who's allowed to do what, appropriately a product decision rather than a security patch, and the limitation is already disclosed in `README.md`.

### ELMER-SEC-012 — Directory-existence oracle in static file serving

- **Severity:** Low
- **Category:** A05 Security Misconfiguration (minor information disclosure)
- **Status:** ✅ Fixed
- **Description:** The custom directory→`index.html` resolution logic ran `os.path.isdir()` on a raw `os.path.join(directory, filename)` before the actual file read (which itself was always safe — Werkzeug's `send_from_directory` uses `safe_join` internally and correctly blocks traversal). A crafted path could make the *pre-check* probe whether a directory exists outside the web root, even though reading its contents remained blocked.
- **Location:** `app/_express.py` (`Server.static`)
- **Impact:** Confirmed **not** exploitable for actual file disclosure — only a minor existence-oracle for directories outside the intended root.
- **Recommendation / Fix applied:** Pre-check now runs through `werkzeug.utils.safe_join` first, closing the oracle outright rather than leaving it as accepted risk, since the fix was low-cost.

---

## Verification

Every finding above marked ✅ Fixed was reproduced against a running
instance before the fix and re-verified after, using the exploitation
steps shown in each entry's Proof of Concept. Two implementation bugs
were caught this way during the audit itself, not left for later
discovery:

1. **ELMER-SEC-003**: the JWT secret override initially worked for
   signing (`login()`) but not verification (`verify()`), which read the
   secret from a different, non-overridden source — caught because the
   regression test explicitly signs under the rotated secret and checks
   verification succeeds, not just that config *looked* right.
2. **ELMER-SEC-005**: the rate limiter's first implementation crashed
   with `ImportError` on every request due to a relative import from a
   dynamically-loaded module with no parent package — caught because the
   verification step checked that requests were actually being *counted*
   and *blocked*, not just that the code ran without raising visibly (the
   new exception-safety fix from ELMER-SEC-008 had, ironically, converted
   the crash into a silent generic 500 that could otherwise have been
   mistaken for "the limiter said no").

Permanent regression tests for all ten fixes live in
`tests/test_security_audit.py`, one per finding ID, and are wired into
`tests/run_all.py`. Full suite result: see the delivery message.
