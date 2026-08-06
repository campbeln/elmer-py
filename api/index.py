"""
##################################################
#
#           Vercel serverless entrypoint
#
##################################################
Version: 2026-08-06

Bridges Elmer's own bootstrap (_index.py) to Vercel's Python runtime.

Vercel's @vercel/python builder looks for a WSGI/ASGI app object at module
scope in app.py, index.py, or wherever tool.vercel.entrypoint in
pyproject.toml points — it imports that module once per cold start and
calls the app object directly for every request. It never calls .run() or
binds a port; there's no "server" in the traditional sense.

_index.py doesn't fit that shape on two counts: its entrypoint is named
with a leading underscore (outside Vercel's search list), and build()/main()
start a *listening* dev server via Flask's .run() rather than exposing a
bare WSGI callable. So this file does what _index.main() does, minus the
part that only makes sense for a long-running process:

  * _index.build()      configures the app (config, middleware, statics) —
                         same as always.
  * _routes.apply(elmer) registers every route module under app/routes —
                         normally triggered by the listen() callback,
                         called directly here instead.
  * elmer.app.status     mirrors on_listening()'s minimal status object.
  * http_server.listen() is never called. Vercel supplies the "listening"
                         part; the module just needs to hand over `app`.

NOTE — statelessness: Elmer's in-process features (elmer.app.cache, the
/elmer/proxy child-API registry, elmer.app.data.response) live in memory on
one instance for the process's lifetime. Serverless functions have no such
guarantee — concurrent invocations may run in different containers, and any
container can be recycled between requests. Routes built on Supabase (or
another external store), like /tickets, are unaffected; routes that depend
on in-memory state across requests are not a good fit for this deployment
target as-is.
"""

import os
import sys

# _index.py lives one directory up from this file (api/index.py -> repo root).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import _index                       # noqa: E402
from app.routes import _routes      # noqa: E402

elmer, http_server = _index.build()

# Equivalent of _index.on_listening(), minus the stdout status banner and
# the outbound heartbeat/registration calls (elmer.app.services.web.api_up /
# .register), which only run when baseElmer=false and would otherwise fire
# a network call at cold start rather than in response to a request.
elmer.app.status = elmer.extend(elmer.app.status, {
    "name": elmer.app.config.get("name"),
    "port": elmer.app.config.get("port"),
    "versions": {
        "ish": elmer.config.ish().ver,
        "app": elmer.app.version,
        "appEx": elmer.app.versionEx,
    },
})
_routes.apply(elmer)

# Vercel's Python runtime looks for this exact module-level name.
app = http_server.flask
