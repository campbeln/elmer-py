# Elmer test suite

Two layers, matching the two ways this project can break:

1. **`tests/*.py`** — Python API tests against the Flask app in-process.
   Fast, no network, no external services.
2. **`tests/browser/`** — jsdom harnesses that execute the `/www` pages'
   **actual JavaScript** (the same React 18.2.0 and Babel 7.23.5 builds the
   CDN tags load) against a live Elmer server backed by a stub Supabase.

The browser layer exists because of a real regression: babel-standalone
runs every `text/babel` script in the *global* scope, so duplicate
top-level `const` declarations across `shared.jsx` and the page scripts
threw `Identifier 'useEffect' has already been declared` and the
management pages rendered nothing. Server-side tests, and even
static-HTML checks, cannot catch that class of bug — only executing the
scripts can.

## Python suite

```bash
python3 tests/run_all.py     # everything, each module in its own process
python3 tests/test_tickets_api.py    # one module standalone
pytest tests/                # also works, if you have pytest
```

No configuration needed: the suite injects an in-memory Supabase
stand-in (`FakeTable`) and sets its own management key.

| Module | Covers |
|---|---|
| `test_ish_library.py` | The ported ish type system: coercions, `resolve`, `extend`, nested `query`, date helpers |
| `test_core_routes.py` | Heartbeat, JWT login/verify, `/elmer/response` lifecycle, proxy-route rejection, request-ID tracing → cache round trip, static serving incl. directory `index.html` |
| `test_tickets_api.py` | Severity ladder + branding meta, validation, full CRUD, the `X-Admin-Key` guard (incl. **fail-closed** when unset), and the "Invalid API key" diagnostics — including that an upstream auth failure returns 502, never a fake 404 |
| `test_vercel_entrypoint.py` | `api/index.py` exposes a Flask WSGI `app` (imported exactly as Vercel would) that serves routes without ever listening |

## Browser suite

```bash
cd tests/browser
npm install      # once; pins the exact React/Babel versions the pages use
npm test         # starts stub Supabase + Elmer, runs the three harnesses
```

Requires Node 18+ and `python3` on PATH. The runner (`run.sh`) starts the
stub PostgREST on `:9999` and Elmer on `:3001`, tears both down by PID on
exit, and never uses `pkill` (a pkill pattern can match the invoking
shell's own command line and kill the test run itself).

| Harness | Covers |
|---|---|
| `test_queue.js` | `/www/managetickets` renders with **zero script errors**; the full 8-column header set (Sev/Subject/Status/Email/Company/Opened/Updated/Ticket ID); each row's view/edit icons target the right pages; sorting the Email column toggles ascending/descending with correct caret; the email and company substring filters narrow the results |
| `test_view_and_status.js` | Deep-linked view page shows the full record; status page updates to `in_progress` **with a message** and now **navigates to the view page on success** (no inline success line); the message then appears in that page's history |
| `test_submit_form.js` | `/www/tickets.html` renders, severity cards select, a P2 ticket submits and is verified stored; the success state shows the public tracking link (`/www/view.html?id=`) and that URL resolves key-free |
| `test_public_view.js` | `/www/view.html?id=` shows the status history newest-first with **no** key gate, and leaks neither reporter email nor description |
| `test_ambient_key.js` | With a valid `X-Admin-Key` injected on every request (reverse proxy / header extension), the key prompt never appears and data loads directly; without it, the gate still guards |
| `test_session_cookie.js` | Unlocking sets a session cookie (no Max-Age — cleared when the browser closes, not just the tab); a fresh page load sharing that cookie skips the prompt entirely; "Forget key" clears it |
| `test_reporter_message.js` | `/www/view.html?id=` lets a reporter add a note with no admin key; it renders with a distinct tag (not a status badge, since it's not a lifecycle transition) on the public page, the staff view page, and the staff status page — see **Known Issues** below for a flake in this harness specifically |
| `test_responsive_css.js` | Static source checks for things jsdom can't verify by rendering (no layout engine): required media queries exist, the Status column carries its nowrap rule, the inline-style-override anti-pattern hasn't crept back into the single-input lookup forms |

`_shared.js` holds the plumbing: a jsdom `ResourceLoader` that serves the
CDN script URLs from local `node_modules`, a `fetch` bridge into the local
server, React-safe input setters, and the key-gate driver.

## Known issues

### Intermittent flake in `test_reporter_message.js`'s status-page block

**Status: mitigated with a retry, root cause not found. Needs real
investigation — this note exists so that doesn't get lost.**

The staff status page's history fetch (the third of three sequential
page-opens in that test file, after the public page and the staff view
page) has intermittently failed to show a just-submitted reporter message
on the first attempt — roughly 1 run in 3 during development, no fixed
pattern found. **This is very likely a test-environment artifact, not an
application bug**: a manual 20-poll / 3-second DOM trace during
development showed the page rendering correctly and stably from the very
first frame with zero flicker, every time it was captured. But "very
likely" isn't "confirmed," and the retry currently in place is a
mitigation, not a fix.

**Current mitigation** (`test_reporter_message.js`, staff status-page
block): up to 3 attempts, each a fresh page load, only failing the test
if all three come up empty. This keeps the suite reliable without masking
a real regression — it still fails loudly on total failure — but it does
not explain *why* the first attempt sometimes doesn't see fresh data.

**Suspected contributing factors, none confirmed:**
- Resource contention: 8 test files run sequentially inside one Node
  process (one `run.sh` invocation), each spinning up jsdom + Babel-
  transpiling a page's scripts — the failure has only ever been observed
  running the full suite, never in isolated single-file runs.
- Possible interaction with `waitress`'s thread pool (`threads=8` in
  `app/_express.py`'s `Server.listen`) under concurrent request load from
  many rapid sequential jsdom-driven fetches.
- Possible interaction with the fixed-window rate limiter
  (`app/middleware/_ratelimit.py`) — every managetickets page load calls
  `/tickets/manage/verify` at least once (cookie check or ambient probe),
  and a full suite run accumulates many such calls; the limit was already
  raised once (15→40/5min) after this suite hit it for real, so it's
  plausible some other timing effect from that same call volume is at
  play even below the current limit.

**Suggested next steps for whoever picks this up:**
1. Add fetch-level timing instrumentation (request-start/response-received
   timestamps) to the status-page block specifically, to distinguish "the
   fetch was slow" from "the fetch silently failed/returned stale data"
   from "the render was slow after a fast fetch."
2. Run the suite with test files isolated into separate Node processes
   (one `node test_x.js` per process, sequenced by the shell rather than
   sharing one Node runtime) to test the resource-contention hypothesis.
3. Try `waitress`'s `threads` value at both higher and lower settings to
   see if it changes the failure rate.
4. Once a fetch-timing signal exists, correlate failure occurrences
   against the rate limiter's internal `_WINDOWS` state (temporarily log
   it) to test the rate-limit-interaction hypothesis.

Do not just delete the retry once this is root-caused — replace it with
whatever the actual fix is, and only then remove the workaround.

## Conventions worth keeping

- Python tests restore whatever they change (storage backend, env vars)
  in `finally` blocks, so modules stay order-independent.
- `run_all.py` runs each module in a separate process so environment
  mutations can't bleed across modules.
- When adding a page or route, add both layers if it has a UI: the Python
  test for the contract, the harness for the page actually running.
