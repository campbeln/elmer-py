"""Minimal PostgREST stand-in for end-to-end tests (port 9999)."""
import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

ROWS = [
    {
        "id": str(uuid.uuid4()),
        "created_at": "2026-08-05T10:00:00+00:00",
        "updated_at": "2026-08-05T10:00:00+00:00",
        "name": "Ada Lovelace", "email": "ada@example.com",
        "company": "Analytical Engines",
        "subject": "Production API outage",
        "description": "Everything is down since 09:40 UTC.",
        "priority": "P1", "status": "open", "trace_id": "t-1",
    },
    {
        "id": str(uuid.uuid4()),
        "created_at": "2026-08-04T15:30:00+00:00",
        "updated_at": "2026-08-04T16:00:00+00:00",
        "name": "Grace Hopper", "email": "grace@example.com",
        "company": None,
        "subject": "Docs question about webhooks",
        "description": "Where do I configure retry backoff?",
        "priority": "P4", "status": "acknowledged", "trace_id": "t-2",
    },
]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        qs = parse_qs(urlsplit(self.path).query)
        out = ROWS
        for key in ("priority", "status", "id"):
            if key in qs:
                want = qs[key][0].split("eq.", 1)[-1]
                out = [r for r in out if str(r.get(key)) == want]
        self._send(200, out)

    def do_PATCH(self):
        from urllib.parse import urlsplit, parse_qs
        qs = parse_qs(urlsplit(self.path).query)
        want = qs.get("id", [""])[0].split("eq.", 1)[-1]
        length = int(self.headers.get("Content-Length", 0))
        patch = json.loads(self.rfile.read(length) or b"{}")
        hit = [r for r in ROWS if r["id"] == want]
        for r in hit:
            r.update(patch)
        self._send(200, hit)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        row = json.loads(self.rfile.read(length) or b"{}")
        row["id"] = str(uuid.uuid4())
        row.setdefault("created_at", "2026-08-06T00:00:00+00:00")
        ROWS.append(row)
        self._send(201, [row])

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9999), Handler).serve_forever()
