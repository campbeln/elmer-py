# Elmer (Python port)

A Python/Flask port of [campbeln/elmer](https://github.com/campbeln/elmer), an
Express-based API scaffold with JWT and Basic authentication, child-API
registration via reverse proxy, request tracing and response caching.

Original work: Copyright (c) 2021-2023 Nick Campbell, MIT licensed. This port
retains that license — see `LICENSE`.

---

## Quick start

```bash
pip install -r requirements.txt
python _index.py dev        # or: python _index.py prod
```

`dev` binds port 3001, `prod` binds 3000 (see `app/config/*.json`). On startup
the app prints its status — name, ports, component versions and the routes it
discovered — as JSON to stdout.

```bash
curl -X GET  http://localhost:3001/
curl -X POST http://localhost:3001/login/admin \
     -H 'Content-Type: application/json' \
     -d '{ "username":"cn", "password":"secret" }'
curl -X GET  http://localhost:3001/www/index.html
```

With Docker:

```bash
docker build . -t elmer/api
docker run --net=api --hostname api.dev -p 45000:3001 -d elmer/api
```

---

## Layout

The Python tree mirrors the JavaScript original file-for-file.

| JavaScript | Python |
|---|---|
| `_index.js` | `_index.py` |
| `app/_app.js` | `app/_app.py` |
| `app/app-ex.js` | `app/app_ex.py` |
| `app/middleware/_requestid.js` | `app/middleware/_requestid.py` |
| `app/middleware/_logapi.js` | `app/middleware/_logapi.py` |
| `app/middleware/_cache.js` | `app/middleware/_cache.py` |
| `app/middleware/_basicauth.js` | `app/middleware/_basicauth.py` |
| `app/middleware/_jwt.js` | `app/middleware/_jwt.py` |
| `app/routes/_routes.js` | `app/routes/_routes.py` |
| `app/routes/elmer.js` | `app/routes/elmer.py` |
| `app/childapi/app-ex.js` | `app/childapi/app_ex.py` |
| `app/childapi/routes/example.js` | `app/childapi/routes/example.py` |
| `app/childapi/routes/example-basic.js` | `app/childapi/routes/example_basic.py` |
| `app/childapi/routes/example-jwt.js` | `app/childapi/routes/example_jwt.py` |
| `libs/ish/ish.js` | `libs/ish/ish.py` |
| `libs/ish/ish.io.net.js` | `libs/ish/ish_io_net.py` |
| `libs/ish/ish.io.web.js` | `libs/ish/ish_io_web.py` |
| `libs/ish/ish.io.csv.js` | `libs/ish/ish_io_csv.py` |
| `libs/ish/ish.type-ex.js` | `libs/ish/ish_type_ex.py` |
| `libs/ish/ish.type.date-format.js` | `libs/ish/ish_type_date_format.py` |
| `libs/ish/ish.type.enum.js` | `libs/ish/ish_type_enum.py` |
| `libs/ish/ish.oop.inherit.js` | `libs/ish/ish_oop_inherit.py` |
| `libs/ish/ish.oop.overload.js` | `libs/ish/ish_oop_overload.py` |
| — | `app/_express.py` *(new — see below)* |

Config files (`app/config/*.json`), static assets under `app/www/` and the
`LICENSE` are carried over unchanged.

Hyphens become underscores because they are not legal in Python module names.

## Dependencies

| Node package | Python equivalent |
|---|---|
| `express` | `Flask` |
| `compression` | `Flask-Compress` |
| `body-parser` | built into Flask |
| `cookie-parser` | built into Flask |
| `express-http-proxy` | `requests` (see `app/app_ex.py`) |
| `node-fetch-commonjs`, `xmlhttprequest` | `requests` |
| `jsonwebtoken` | `PyJWT` |
| `formidable` | `Werkzeug` (via Flask) |
| `jszip` | `zipfile` (stdlib) |
| `ip` | `socket` (stdlib) |

---

## Porting decisions

Four choices are worth understanding before reading the code.

### 1. `app/_express.py` — an Express compatibility layer

Elmer is written in thoroughly Express-shaped idioms: handlers take
`(oRequest, oResponse)`, middleware takes `(oRequest, oResponse, fnContinue)`,
routers mount via `server.use("/prefix", router)`, and responses are written
with `oResponse.status(200).json({...})`.

Rewriting each route into idiomatic Flask would have worked, but it would have
destroyed any line-by-line correspondence with the original source — making the
port hard to diff, review or keep in sync upstream. Instead, `_express.py`
reproduces those few Express primitives (`Request`, `Response`, `Router`,
`Server`, and a middleware chain runner) on top of Flask. Every other ported
file then reads as a near-direct translation of its JavaScript counterpart.

This is the only file with no JS ancestor.

### 2. Runtime route mounting

Express lets you mount routers whenever you like. Flask freezes its URL map
once the first request has been served.

That matters because `/elmer/proxy` exists precisely so that child APIs can
register themselves against an **already running** server. A naive port throws
`AssertionError: The setup method 'register_blueprint' can no longer be
called...` on every child registration.

`Server.mount()` therefore branches: routers added before startup become normal
Flask blueprints, while routers added afterwards go into a runtime dispatch
table served by a catch-all installed by `Server.install_catchall()`. Each
dynamic entry gets its own Werkzeug `Map`, so path parameters and method
matching behave the same either way. Werkzeug ranks a `<path:...>` rule below
concrete rules, so the catch-all only runs when nothing static matches.

### 3. Body parsing and the proxy

The JS carries a long comment (and a Stack Overflow link) about excluding
proxied routes from `body-parser`, because parsing consumes the request stream
before the proxy can forward it.

Flask parses bodies lazily, on access, so the problem does not arise. The
proxy in `app_ex.py` reads the raw body directly and forwards it untouched.
`configBodyParser` survives as the place where the configured `uploadLimitMb`
ceiling is applied, which is the remaining half of what it did.

### 4. `libs/ish` is ported selectively

The vendored ishJS is roughly 33,000 lines, the large majority of it browser
concerns the server can never reach — DOM manipulation, Vue bindings, clipboard
and modal widgets, tooltips, CSS helpers, XLSX and punycode.

I ported the surface the application actually calls, determined by grepping the
app for `$elmer.*` usage rather than by guesswork. That covers `extend`,
`resolve`, `type.query`, `type.uuid`, the `str`/`int`/`float`/`bool`/`arr`/
`obj`/`fn`/`date`/`symbol`/`is` families, `io.net`, `io.web.queryString`,
`io.csv`, `type.enum` and the `oop` helpers.

`$elmer.io.xlsx` is **not** implemented. It is referenced only by the
commented-out example route in `app/childapi/routes/example.py`. If you need
it, `openpyxl` is the natural substitute.

Because ishJS is JavaScript, several of its coercions are deliberately loose —
`bool.mk("true")` is `True`, `int.mk("42abc")` falls back to the default. Those
semantics are preserved rather than "corrected", since application logic
depends on them.

---

## Intentional behavioural deviations

Everything else aims to match the original. These do not.

**Trace ID generation (`app/middleware/_requestid.py`).** When a request
arrives with no `X-Request-Id` / `X-Correlation-Id` / `X-Trace-Id`, the
middleware mints a UUID — but in the original the subsequent `extend()` merges
an object carrying an empty-string `id` *over* that fresh UUID, blanking it.
Every response then caches under an empty key and the `/elmer/cache/*` routes
silently 404. This port applies the resolved id last so it always wins. The
same ordering quirk appears to exist in the JS; treat this as a fix, not a
faithful translation.

**Credential comparison.** `_basicauth.py` and `_jwt.py` use
`hmac.compare_digest` for username and password checks. The original uses `===`.
Both keep the original's randomised startup-uptime delay.

**Naming.** `oRequest.$trace` becomes `request.trace`, and `ish.type.is`
becomes `ish.type.is_`, since `$` is not a legal identifier character and `is`
is a reserved keyword in Python. Methods are exposed under both `snake_case`
and the original `camelCase` where application code calls them by name.

**Async.** The JS marks most handlers `async` but rarely awaits anything
meaningful. The port is synchronous, except `childapi/routes/example.py`, whose
delayed-response demo uses `threading.Timer` in place of `setTimeout`.

---

## Adding a route

Drop a module into `app/routes/` exposing `apply(elmer, router, base_router)`.
`app/routes/_routes.py` discovers and registers it automatically, mounting it
at a URL derived from the filename.

```python
def apply(elmer, router, base_router=None):
    @router.get("/byid/:id")
    def _by_id(request, response):
        response.status(200).json({"id": elmer.type.int.mk(request.params.get("id"))})
```

Return `False` to tell Elmer not to register the router, or return a different
router to register that one instead — same contract as the original.

To protect a route, set `router.elmer` before defining handlers:

```python
router.elmer = elmer.extend(
    router.elmer, {"security": elmer.resolve(elmer.app.config, "security.jwt")}
)
```

---

## Verification

The port was exercised both through Flask's test client and as a live server:

- heartbeat and registration branches of `/`
- `/elmer/proxy` child registration, including the disallowed-route 409
- the full `/elmer/response` create / update / read / 404 lifecycle
- every `/elmer/cache/*` inspect and clear route
- JWT login and verify, with valid and invalid credentials
- Basic auth across valid, invalid and absent credentials
- request-ID tracing, both generated and honouring an inbound header
- static file serving from `/www`

> **Security note:** `app/config/base.json` ships with the original's example
> secrets and user list. Replace them before any real deployment.

---

## Support tickets (Supabase)

`app/routes/tickets.py` adds a Supabase-backed support ticket API, auto-mounted
at `/tickets`, with a matching web form served at `/www/tickets.html`.

**Setup**

1. Create a Supabase project and run `supabase/migrations/0001_tickets.sql`
   (SQL editor or `supabase db push`). It creates the `tickets` table, the
   `P1`–`P4` priority enum, lifecycle statuses, indexes, an `updated_at`
   trigger, and enables RLS with no public policies — so all access flows
   through this API with the service-role key.
2. Provide credentials via `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` environment
   variables, or `"supabase": { "url", "serviceKey" }` in `app/config`.
   Environment variables win, keeping the key out of committed config.

**Endpoints**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/tickets` | Submit a ticket (`name`, `email`, `subject`, `description`, optional `company`, `priority` P1–P4, default P4) |
| `GET` | `/tickets?priority=&status=&limit=&offset=` | List tickets, newest first |
| `GET` | `/tickets/<uuid>` | Read one ticket |
| `POST` | `/tickets/<uuid>/status` | Advance lifecycle: open → acknowledged → in_progress → resolved → closed |
| `GET` | `/tickets/meta/priorities` | The severity ladder + statuses, consumed by the form |

Validation mirrors the DB constraints (required fields, email shape, length
ceilings, priority whitelist) so bad input fails fast with a useful message.
Each stored ticket records the request's `trace_id`, tying it into Elmer's
`X-Request-Id` tracing and `/elmer/cache/*` inspection.

**Priorities**

| Code | Label | Definition |
|---|---|---|
| P1 | Critical | Complete production service outage, active security incident, data loss, or failure of core production functionality with material business impact and no reasonable workaround. |
| P2 | High | Major degradation of core functionality or partial loss of production service that materially impacts use of the Platform. |
| P3 | Medium | Non-critical issue with limited impact, minor degradation, or issue where a reasonable workaround is available. |
| P4 | Low / Request | General inquiry, cosmetic issue, documentation question, enhancement request, or other issue with no material operational impact. |

**Web form** — `app/www/tickets.html` is a self-contained React page (CDN,
no build step) served by Elmer itself, so its relative `/tickets` calls hit
the same origin with no CORS work. It fetches the severity ladder from
`/tickets/meta/priorities` at load, so form and API cannot drift apart.

---

## Deploying to Vercel

Vercel's Python builder needs a WSGI app object exposed at module scope in
`app.py`, `index.py`, or a path set via `tool.vercel.entrypoint` in
`pyproject.toml` — it imports that module once per cold start and calls the
app directly per request. It never calls `.run()` or binds a port.

`_index.py` doesn't fit that shape on two counts: it's outside Vercel's
default search list (leading underscore), and `build()`/`main()` start a
*listening* dev server rather than exposing a bare callable. `api/index.py`
bridges the two — it runs the same `_index.build()` bootstrap and route
registration, then hands over `http_server.flask` as `app` without ever
calling `.listen()`. `vercel.json` routes every path to that function.

```bash
npm i -g vercel      # if you don't have the CLI yet
cd elmer-py
vercel               # deploys; follow the prompts
```

Set `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` (if using the ticket API) as
[Environment Variables](https://vercel.com/docs/environment-variables) in
the Vercel project settings — not in a committed config file.

**Statelessness matters here.** Elmer's in-process features —
`elmer.app.cache`, the `/elmer/proxy` child-API registry,
`elmer.app.data.response` — live in memory for one process's lifetime.
Serverless functions offer no such guarantee: concurrent invocations may
land in different containers, and any container can be recycled between
requests. Routes backed by an external store (like `/tickets`, on Supabase)
work as expected; routes that depend on in-memory state persisting *across*
requests — the proxy registry and cache being the main ones — are not a
good fit for this deployment target without moving that state to Supabase,
Redis, or similar.
