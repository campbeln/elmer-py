"""
Shared helpers for the Elmer test suite.

Builds the application once per process (via _index.build + route
registration) and exposes it through a Flask test client, plus an in-memory
stand-in for the Supabase table so the ticket routes can be exercised
without network access.

Every test module in this directory works two ways:

    python tests/test_<name>.py     # standalone, prints a summary
    pytest tests/                   # standard pytest collection
"""

import os
import sys
import uuid

# Make the project root importable no matter where the tests are run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: The management key every test uses. Set before the app is built so the
#: admin guard (which reads the environment per-request) sees it.
ADMIN_KEY = "test-admin-key"
GOOD_HEADERS = {"X-Admin-Key": ADMIN_KEY}
BAD_HEADERS = {"X-Admin-Key": "wrong-key"}

_cache = {}


def get_app():
    """Build (once) and return (elmer, server, client)."""
    if "app" not in _cache:
        os.environ.setdefault("TICKETS_ADMIN_KEY", ADMIN_KEY)
        sys.argv = ["_index.py", "dev"]
        import _index
        elmer, server = _index.build()
        _index.on_listening()
        _cache["app"] = (elmer, server, server.flask.test_client())
    return _cache["app"]


class FakeTable:
    """In-memory SupabaseTable stand-in with PostgREST-shaped responses."""

    def __init__(self):
        self.rows = []

    def _ok(self, status, data):
        from libs.ish.ish import Obj
        return Obj({"ok": True, "status": status, "data": data})

    _clock = [0]   # class-level counter -> distinct, ordered timestamps

    def insert(self, row):
        row = dict(row)
        row["id"] = str(uuid.uuid4())
        FakeTable._clock[0] += 1
        row.setdefault("created_at",
                       "2026-01-01T00:00:%02d+00:00" % FakeTable._clock[0])
        row.setdefault("updated_at", row["created_at"])
        self.rows.append(row)
        return self._ok(201, [row])

    def select(self, filters=None, order=None, limit=None, offset=None):
        out = self.rows
        for key, value in (filters or {}).items():
            if key == "select":
                continue
            want = value.split("eq.", 1)[-1]
            out = [r for r in out if str(r.get(key)) == want]
        out = list(reversed(out))
        if offset:
            out = out[offset:]
        if limit is not None:
            out = out[:limit]
        return self._ok(200, out)

    def update(self, filters, patch):
        want = filters["id"].split("eq.", 1)[-1]
        hit = [r for r in self.rows if r["id"] == want]
        for r in hit:
            r.update(patch)
        return self._ok(200, hit)


class UnauthorizedTable:
    """Simulates Supabase rejecting the key — what a bad credential returns."""

    def _err(self):
        from libs.ish.ish import Obj
        return Obj({"ok": False, "status": 401, "data": {
            "message": "Invalid API key",
            "hint": "Double check your Supabase `anon` or `service_role` API key.",
        }})

    def insert(self, row):
        return self._err()

    def select(self, filters=None, order=None, limit=None, offset=None):
        return self._err()

    def update(self, filters, patch):
        return self._err()


def use_table(table, name="tickets"):
    """Swap a ticket route storage backend; returns the previous one.

    name: "tickets" or "ticket_status_updates" (matches _table's cache keys).
    """
    elmer, _, _ = get_app()
    key = name + "_table"
    previous = elmer.app.data.get(key)
    elmer.app.data[key] = table
    return previous


def make_ticket(client, **overrides):
    """Create a valid ticket through the API; returns the response JSON."""
    import json
    body = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "subject": "Test ticket",
        "description": "Created by the test suite.",
        "priority": "P3",
    }
    body.update(overrides)
    response = client.post("/tickets/", json=body)
    return response.status_code, json.loads(response.get_data(as_text=True))


def run_module(module_globals):
    """Standalone runner: execute every test_* function in a module."""
    tests = [(name, fn) for name, fn in sorted(module_globals.items())
             if name.startswith("test_") and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except AssertionError as error:
            failures.append((name, error))
            print("  FAIL  %s: %s" % (name, error))
        except Exception as error:  # noqa: BLE001 - report, don't crash the run
            failures.append((name, error))
            print("  ERROR %s: %r" % (name, error))
    print("%d passed, %d failed" % (len(tests) - len(failures), len(failures)))
    return 1 if failures else 0
