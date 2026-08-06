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
| `POST` | `/tickets/<uuid>/status` | Advance lifecycle (open → acknowledged → in_progress → resolved → closed), with an optional `message` (≤2000 chars) recorded in the `ticket_status_updates` history table |
| `GET` | `/tickets/meta/priorities` | The severity ladder + statuses + branding, consumed by the forms |
| `GET` | `/tickets/<uuid>/public` | **No admin key.** Read-only status view: subject, priority, lifecycle, timestamps, and the status-update history (newest first). Reporter identity and description are withheld — the unguessable UUID acts as a shareable capability link, so it must not hand out PII. Backs `/www/view.html?id=` |

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
calling `.listen()`.

`vercel.json` deliberately contains **no `builds` property** — Vercel's
zero-configuration detection picks up `api/index.py` as a Python function
on its own, and a `builds` entry would make Vercel ignore all dashboard
Build & Development Settings (emitting a deploy-time warning about it).
The catch-all uses the `routes` property rather than the more modern
`rewrites`, and that choice is load-bearing: rewrites apply *after*
Vercel's filesystem check, which in a no-framework project serves repo
files — including `app/config/*.json` — as static assets at their raw
URLs. `routes` (with no `handle: filesystem` entry) sends every request
to the function before any static serving happens.
`tests/test_vercel_entrypoint.py` guards both properties.

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


### Troubleshooting: "Invalid API Key"

If `/tickets` returns Supabase's own `Invalid API Key` message (surfaced
through this API's `details` field), the request *is* reaching Supabase —
Elmer's own "Ticket storage is not configured" 503 would show instead if
`SUPABASE_URL`/`SUPABASE_SERVICE_KEY` weren't set at all. So the fix is on
the credentials, not the code. In order of likelihood:

1. **Redeploy after setting/changing env vars.** Vercel bakes environment
   variables in at deploy time; saving them in the dashboard does not
   retroactively apply to an already-running deployment. Trigger a new
   deployment (`vercel --prod`, or **Redeploy** in the dashboard) after any
   change.
2. **Check the environment scope.** Vercel env vars are scoped to
   Production / Preview / Development independently — confirm
   `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are enabled for whichever
   scope serves the URL you're hitting.
3. **Re-copy the key fresh**, watching for accidental leading/trailing
   whitespace or quotes from pasting. Supabase now issues two key formats
   side by side — legacy JWT `service_role` keys (Dashboard → **Settings →
   API Keys → Legacy API Keys**) and the newer `sb_secret_...` keys
   (**Settings → API Keys → API Keys → Secret keys**). Either works as
   `SUPABASE_SERVICE_KEY`; legacy keys are slated for deprecation by the
   end of 2026, so prefer the `sb_secret_...` key for new setups. Never use
   the `sb_publishable_...` or legacy `anon` key here — those lack the
   privileges this API needs and Supabase's own docs warn a secret key
   used from a browser is rejected outright, so keep it server-side only.
4. **Confirm the URL and key are from the same project.** Mixing a URL
   from one Supabase project with a key from another produces exactly this
   error.
5. **Isolate Elmer from Supabase** by testing the pair directly:
   ```bash
   curl "https://YOUR_PROJECT_REF.supabase.co/rest/v1/tickets?select=id&limit=1" \
        -H "apikey: YOUR_KEY" \
        -H "Authorization: Bearer YOUR_KEY"
   ```
   If this also fails, the problem is entirely the Supabase credentials —
   nothing to do with Vercel or Elmer. If it succeeds but the deployed API
   still fails, the environment variable isn't reaching the deployment
   (see points 1–2).

---

## Ticket management console

Three staff-facing forms under `app/www/managetickets/`, in the same visual
system as the public submission form, covering the rest of the `/tickets`
API:

| URL | Backs | Purpose |
|---|---|---|
| `/www/managetickets` | `GET /tickets` | Filterable queue (severity, status), newest first |
| `/www/managetickets/view` | `GET /tickets/<uuid>` | Full record for one ticket; deep-linkable via `?id=` |
| `/www/managetickets/status` | `POST /tickets/<uuid>/status` | Advance a ticket through its lifecycle |

They share one stylesheet and one component file (`shared.css`,
`shared.jsx`: key gate, nav, badges, fetch wrapper), and cross-link — queue
rows open the view page, which links to the status page, carrying the
ticket id in the query string.

### Management key

The management surface requires a second secret, separate from the Supabase
key: set the `TICKETS_ADMIN_KEY` environment variable (or
`tickets.adminKey` in `app/config`; the environment wins). The guard
applies **server-side** to `GET /tickets`, `GET /tickets/<uuid>` and
`POST /tickets/<uuid>/status`, which must carry a matching `X-Admin-Key`
header — the forms are a convenience on top, not the enforcement point.
`POST /tickets` (submission) and `/tickets/meta/priorities` remain public.

The guard **fails closed**: with no key configured, management endpoints
return `503 Ticket management is not enabled` rather than opening up.
Comparison uses `hmac.compare_digest`. Each form gates its UI through
`POST /tickets/manage/verify` before loading data; the entered key is held
in page memory only — never persisted, never placed in a URL.

If the environment already supplies a valid `X-Admin-Key` on requests — a
reverse proxy in front of the console, a header-injecting browser
extension, or an embedding tool — the forms detect this automatically: on
load they probe `verify` with no key attached, and when the injected
header passes, the "Management key required" prompt is skipped and all
later API calls omit the header so the same injection authenticates them
in transit. Browsers can't set custom headers on their own, so a plain
visit still sees the prompt, and server-side enforcement is unchanged
either way.

Note the honest limits of this scheme: it's one shared bearer secret over
whatever transport you serve — fine for a small internal console behind
HTTPS, but it is not per-user auth, and anyone holding the key can do
everything. For per-person access or audit trails, put the console behind
the JWT login flow Elmer already ships instead.

### Branding

The wordmark on all four forms comes from config rather than being
hard-coded: `"branding": { "name": "CNRZ", "area": "Support" }` in
`app/config/base.json`, served to the pages via
`GET /tickets/meta/priorities`. Change the config values and every form
follows; if the API is unreachable the pages fall back to the same CNRZ
default baked into their source.

---

## Tests

The project ships its test suite under `tests/` — a Python API layer
(`python3 tests/run_all.py`, no setup required) and a browser layer
(`cd tests/browser && npm install && npm test`) whose jsdom harnesses
execute the `/www` pages' actual JavaScript against a live server and a
stub Supabase. See `tests/README.md` for coverage details and the
conventions for extending it.

---

## Status history & public tracking

Every status change is recorded in `ticket_status_updates`
(`supabase/migrations/0002_ticket_status_updates.sql` — apply after 0001),
with an optional message entered on the management status page. The
management view page and `GET /tickets/<uuid>` include the full history
newest-first; a history-read failure degrades to an empty list with an
`updates_error` flag rather than failing the ticket read, and a
history-write failure after a successful status change is reported as
`history_error` rather than erroring (the change itself already took).

`/www/view.html?id=<uuid>` is the public tracking page: no admin key, no
gate, backed by `GET /tickets/<uuid>/public`. Queue rows in the
management console are click-through to the view page. After a successful
submission, `/www/tickets.html` shows the reporter their absolute tracking
URL with a copy button (clipboard API where available, `execCommand`
fallback for non-secure contexts).

---

## Queue, sorting, filtering, and status navigation

The management queue (`/www/managetickets`) now shows Email, Company, and
Updated Date columns alongside the original Severity/Subject/Status/Opened/
Ticket ID. Severity, Status, Email, Company, Opened, and Updated Date
headers are clickable and toggle ascending/descending — sorting happens
client-side over the already-fetched page, so it's instant and independent
of which server-side filters are active. Each row carries small view/edit
icons under its Ticket ID (view → the read-only detail page, edit → the
status page); the icons stop click propagation so they don't also trigger
the row's own navigate-to-view behavior.

Two new filters, **Email contains** and **Company contains**, do
case-insensitive substring matching — searching `@gmail.com` returns every
matching address. These push down to Supabase via PostgREST's `ilike`
operator (`GET /tickets?email=...&company=...`) rather than filtering
client-side, so they scale the same way the existing exact-match
priority/status filters do.

Submitting a status update on `/www/managetickets/status/?id=` now
navigates straight to `/www/managetickets/view/?id=` on success, landing
on a page that already shows the just-made update in its history — rather
than staying on the form with an inline confirmation.

---

## Security audit (2026-08-06)

A full security audit was performed against this codebase — dependency
scan, secret/pattern search, and an OWASP Top 10 assessment, with every
finding verified against a running instance both before and after its
fix. Two Critical, internet-exploitable findings were closed (an
unauthenticated endpoint that leaked admin-gated data and issued JWTs,
and an unauthenticated SSRF primitive), along with three High and five
Medium findings. Full report, including Proof of Concept reproductions
and the two implementation bugs the verification step itself caught:
**[`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md)**.

### New environment variables from the audit

| Variable | Purpose | Required? |
|---|---|---|
| `ELMER_ADMIN_KEY` | Gates `/elmer/proxy` and all `/elmer/cache/*` routes — previously unauthenticated. Fails closed (503) if unset. | Yes, before deploying — these routes refuse all requests without it. |
| `ELMER_JWT_SECRET` | Overrides the JWT signing secret shipped in `app/config/base.json`. That shipped value is an example only and must be treated as public. | **Strongly recommended** for any real deployment. |
| `ELMER_JWT_LOCAL_SECRET` | Overrides the paired local-request secret (currently dormant — the local-request bypass path is disabled in this port). | Optional. |

**Breaking change:** child-API self-registration (`POST /elmer/proxy`)
now requires a matching `X-Admin-Key` header. Any service that self-
registers on startup needs to be updated to send it.

On startup, the app checks whether the shipped example JWT secret or any
shipped example password is still in use and prints a loud warning to
stderr if so — it never blocks startup, only nudges.

---

## Responsive design, session-cookie key storage, notification stubs, and end-user updates (2026-08-06)

### Responsive CSS across `/www/`

Every page under `/www/` now targets mobile and desktop as first-class
layouts (standing project convention going forward — see below). Fixed
along the way: three pages (`view.html`, `managetickets/view`,
`managetickets/status`) used `className="filters" style={{
gridTemplateColumns: "1fr auto" }}` for their single-input lookup forms —
an inline style, which always overrides a later CSS media query
regardless of viewport, silently defeating mobile responsiveness on
exactly those forms. Replaced with a dedicated `.filters-single` class
carrying its own breakpoint. The management queue table is now wrapped
for horizontal scroll on narrow viewports, inputs/buttons hit real touch
targets, and `font-size: 16px` on form fields prevents iOS Safari's
auto-zoom-on-focus.

**Standing project convention:** all web interfaces built for this
project use responsive CSS by default, with mobile and desktop both
treated as first-class targets — an interface only skips this if its own
requirements say otherwise.

### Session-cookie management key

`/www/managetickets/*` no longer re-prompts for the management key on
every page load. `KeyGate` now tries, in order: a session cookie from a
previous unlock this browser session, then the existing ambient
X-Admin-Key probe (reverse proxy / header extension), then the manual
prompt — whose successful entry is saved to the cookie. It's a genuine
*session* cookie (no Max-Age/Expires), cleared when the browser itself
closes, not just the tab. A "Forget key" control in the nav bar clears it
sooner. Necessarily JS-readable (not HttpOnly), since it's set from
client-side code with no server round trip in the "remember" step — an
accepted trade-off for an internal console.

### Status column no longer wraps

Fixed at the badge level (`white-space: nowrap` on `.status-badge`) and
reinforced with a dedicated `col-status` class on the queue table's
header and cells.

### Notification stubs

`app/routes/tickets.py` now calls a `_notify()` hook on ticket creation,
staff status updates, and reporter messages — a stub, not a real
integration: unless `NOTIFY_WEBHOOK_URL` (or `notifications.webhookUrl`
in config) is set, it's a complete no-op that costs nothing on the hot
path. When configured, it POSTs exactly what a real notification would
need: the event type, the `/www/view.html?id=` tracking link, and the
latest status/message/timestamp. Delivery is best-effort with a short
timeout — a slow or broken notification target can never fail the
ticket operation that triggered it.

### End-user messages via `/www/view.html?id=`

Reporters can now add information to their own ticket from the public
tracking page — same message-collection UX as the staff status page, but
scoped to a note, not a status change: `POST /tickets/<uuid>/reporter-
message` (public, rate-limited, no admin key) records an entry with
`author: "reporter"` and `status: null` in the same `ticket_status_
updates` history table staff updates already use — migration
`0003_ticket_updates_author.sql` adds the `author` column and makes
`status` nullable for exactly this case. After submitting, the page
returns to its normal read-only view showing the new message inline.

Reporter-authored entries render with a distinct "Reporter note" tag
instead of a status badge (since they're not a lifecycle transition), on
all three surfaces that show ticket history: the public tracking page,
the staff view page, and — newly — the staff status page, which didn't
show any history before this change and now displays it read-only above
the status-update form.
