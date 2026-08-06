"""Minimal PostgREST stand-in for end-to-end tests (port 9999).

Serves two tables under /rest/v1/: tickets and ticket_status_updates,
enough PostgREST semantics (eq filters, insert-with-representation,
patch) for the Elmer ticket routes. Reads return newest-inserted first,
matching the created_at.desc ordering the API requests.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

_BASE_TIME = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
_CLOCK = [0]


def _now():
    """Distinct, strictly increasing timestamps so ordering is testable."""
    _CLOCK[0] += 1
    return (_BASE_TIME + timedelta(seconds=_CLOCK[0])).isoformat()


TABLES = {
    "tickets": [
        {
            "id": str(uuid.uuid4()),
            "created_at": _now(), "updated_at": _now(),
            "name": "Ada Lovelace", "email": "ada-private@example.com",
            "company": "Analytical Engines",
            "subject": "Production API outage",
            "description": "Everything is down since 09:40 UTC.",
            "priority": "P1", "status": "open", "trace_id": "t-1",
        },
        {
            "id": str(uuid.uuid4()),
            "created_at": _now(), "updated_at": _now(),
            "name": "Grace Hopper", "email": "grace@example.com",
            "company": None,
            "subject": "Docs question about webhooks",
            "description": "Where do I configure retry backoff?",
            "priority": "P4", "status": "acknowledged", "trace_id": "t-2",
        },
    ],
    "ticket_status_updates": [],
}


class Handler(BaseHTTPRequestHandler):
    def _table(self):
        name = urlsplit(self.path).path.rsplit("/", 1)[-1]
        return TABLES.get(name)

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _filters(self):
        qs = parse_qs(urlsplit(self.path).query)
        return {k: v[0].split("eq.", 1)[-1] for k, v in qs.items()
                if k not in ("select", "order", "limit", "offset")
                and v[0].startswith("eq.")}

    def do_GET(self):
        rows = self._table()
        if rows is None:
            return self._send(404, {"message": "relation does not exist"})
        out = rows
        for key, want in self._filters().items():
            out = [r for r in out if str(r.get(key)) == want]
        # newest-inserted first ~ created_at.desc
        self._send(200, list(reversed(out)))

    def do_POST(self):
        rows = self._table()
        if rows is None:
            return self._send(404, {"message": "relation does not exist"})
        length = int(self.headers.get("Content-Length", 0))
        row = json.loads(self.rfile.read(length) or b"{}")
        row["id"] = str(uuid.uuid4())
        row.setdefault("created_at", _now())
        rows.append(row)
        self._send(201, [row])

    def do_PATCH(self):
        rows = self._table()
        if rows is None:
            return self._send(404, {"message": "relation does not exist"})
        want = self._filters().get("id", "")
        length = int(self.headers.get("Content-Length", 0))
        patch = json.loads(self.rfile.read(length) or b"{}")
        hit = [r for r in rows if r.get("id") == want]
        for r in hit:
            r.update(patch)
            r["updated_at"] = _now()
        self._send(200, hit)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9999), Handler).serve_forever()
