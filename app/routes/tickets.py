"""
##################################################
#
#           Support ticket routes
#
##################################################
Version: 2026-08-05

Supabase-backed end-user support tickets, served through the Elmer facade.
Auto-registered by app/routes/_routes.py at /tickets.

Priorities follow the published severity ladder:

    P1 Critical     Complete production service outage, active security
                    incident, data loss, or failure of core production
                    functionality with material business impact and no
                    reasonable workaround.
    P2 High         Major degradation of core functionality or partial loss
                    of production service that materially impacts use of the
                    Platform.
    P3 Medium       Non-critical issue with limited impact, minor
                    degradation, or issue where a reasonable workaround is
                    available.
    P4 Low/Request  General inquiry, cosmetic issue, documentation question,
                    enhancement request, or other issue with no material
                    operational impact.

Storage is Supabase's PostgREST endpoint, addressed with the service-role
key. Configure via app/config/*.json ("supabase": { "url", "serviceKey" })
or the SUPABASE_URL / SUPABASE_SERVICE_KEY environment variables (the
environment wins, so secrets can stay out of committed config).

Endpoints (curl examples assume the dev port):

  curl -X POST http://localhost:3001/tickets \
       -H 'Content-Type: application/json' \
       -d '{ "name":"Ada", "email":"ada@example.com",
             "subject":"API down", "description":"…", "priority":"P1" }'
  curl -X GET  'http://localhost:3001/tickets?priority=P1&status=open&limit=20'
  curl -X GET   http://localhost:3001/tickets/<id>
  curl -X POST  http://localhost:3001/tickets/<id>/status \
       -H 'Content-Type: application/json' -d '{ "status":"resolved" }'
  curl -X GET   http://localhost:3001/tickets/meta/priorities
"""

import hmac
import os
import re

import requests

from libs.ish.ish import Obj

#: The severity ladder, verbatim. Served at /tickets/meta/priorities so the
#: web form and the API can never drift apart.
PRIORITIES = [
    Obj({
        "code": "P1",
        "label": "Critical",
        "description": (
            "Complete production service outage, active security incident, "
            "data loss, or failure of core production functionality with "
            "material business impact and no reasonable workaround."
        ),
    }),
    Obj({
        "code": "P2",
        "label": "High",
        "description": (
            "Major degradation of core functionality or partial loss of "
            "production service that materially impacts use of the Platform."
        ),
    }),
    Obj({
        "code": "P3",
        "label": "Medium",
        "description": (
            "Non-critical issue with limited impact, minor degradation, or "
            "issue where a reasonable workaround is available."
        ),
    }),
    Obj({
        "code": "P4",
        "label": "Low / Request",
        "description": (
            "General inquiry, cosmetic issue, documentation question, "
            "enhancement request, or other issue with no material "
            "operational impact."
        ),
    }),
]

PRIORITY_CODES = [entry.code for entry in PRIORITIES]
STATUSES = ["open", "acknowledged", "in_progress", "resolved", "closed"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

#: Field length ceilings, mirroring the DB check constraints so bad input
#: fails fast at the API with a useful message instead of a PostgREST error.
_LIMITS = {"name": 200, "subject": 300, "description": 10000, "company": 200}


class SupabaseTable:
    """Minimal PostgREST client for one table.

    Kept deliberately small and injectable: tests (and any future backend
    swap) replace this object on the module rather than mocking HTTP.
    """

    def __init__(self, url, service_key, table):
        self.base = url.rstrip("/") + "/rest/v1/" + table
        self.headers = {
            "apikey": service_key,
            "Authorization": "Bearer " + service_key,
            "Content-Type": "application/json",
        }

    def _wrap(self, response):
        try:
            data = response.json()
        except ValueError:
            data = None
        return Obj({
            "ok": response.ok,
            "status": response.status_code,
            "data": data,
        })

    def _call(self, method, **kwargs):
        """Issue the request, shaping transport failures like bad responses."""
        try:
            return self._wrap(requests.request(
                method, self.base, timeout=15, **kwargs
            ))
        except requests.RequestException as error:
            return Obj({
                "ok": False,
                "status": 0,
                "data": {"error": "Supabase is unreachable.",
                         "details": str(error)},
            })

    def insert(self, row):
        headers = dict(self.headers, Prefer="return=representation")
        return self._call("POST", json=row, headers=headers)

    def select(self, filters=None, order=None, limit=None, offset=None):
        params = dict(filters or {})
        params["select"] = "*"
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        if offset:
            params["offset"] = str(offset)
        return self._call("GET", params=params, headers=self.headers)

    def update(self, filters, patch):
        headers = dict(self.headers, Prefer="return=representation")
        return self._call("PATCH", params=filters, json=patch, headers=headers)


def _table(elmer, name="tickets"):
    """Resolve a configured Supabase table, memoised on elmer.app.data.

    Environment variables override config so deployments can keep the
    service-role key out of the repo. Tests inject fakes under the same
    keys ('tickets_table', 'ticket_status_updates_table').
    """
    cache_key = name + "_table"
    existing = elmer.resolve(elmer.app.data, cache_key)
    if existing is not None:
        return existing

    url = (os.environ.get("SUPABASE_URL")
           or elmer.type.str.mk(elmer.resolve(elmer.app.config, "supabase.url")))
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or elmer.type.str.mk(
               elmer.resolve(elmer.app.config, "supabase.serviceKey")))

    if not url or not key:
        return None

    elmer.app.data[cache_key] = SupabaseTable(url, key, name)
    return elmer.app.data[cache_key]


def _validate_ticket(elmer, body):
    """Validate a submission, returning (row, errors)."""
    errors = []
    row = Obj()

    for field, required in (("name", True), ("email", True), ("company", False),
                            ("subject", True), ("description", True)):
        value = elmer.type.str.mk(body.get(field)).strip()
        limit = _LIMITS.get(field)
        if required and not value:
            errors.append("'%s' is required." % field)
        elif limit and len(value) > limit:
            errors.append("'%s' must be %d characters or fewer." % (field, limit))
        elif value:
            row[field] = value

    if row.get("email") and not _EMAIL_RE.match(row.email):
        errors.append("'email' must be a valid email address.")

    priority = elmer.type.str.mk(body.get("priority"), "P4").strip().upper()
    if priority not in PRIORITY_CODES:
        errors.append("'priority' must be one of %s." % ", ".join(PRIORITY_CODES))
    else:
        row.priority = priority

    return row, errors


def _admin_key(elmer):
    """Resolve the management key; env wins over config, mirroring Supabase."""
    return (os.environ.get("TICKETS_ADMIN_KEY")
            or elmer.type.str.mk(
                elmer.resolve(elmer.app.config, "tickets.adminKey")))


def _admin_guard(elmer, request, response):
    """Enforce the X-Admin-Key header on management endpoints.

    Returns True when the request may proceed; otherwise writes the error
    response and returns False. Fails CLOSED: with no key configured, the
    management surface is off entirely rather than open to everyone.
    """
    configured = _admin_key(elmer)
    if not configured:
        elmer.app.error.response(
            response,
            Obj({
                "message": "Ticket management is not enabled.",
                "details": ("Set the TICKETS_ADMIN_KEY environment variable "
                            "(or tickets.adminKey in app/config) to enable "
                            "the management endpoints."),
            }),
            elmer.io.net.status.serverError.serviceUnavailable,
        )
        return False

    supplied = elmer.type.str.mk(
        elmer.type.obj.get(request.headers, "X-Admin-Key"))
    if not supplied or not hmac.compare_digest(supplied, configured):
        elmer.app.error.response(
            response, "A valid X-Admin-Key header is required.",
            elmer.io.net.status.clientError.unauthorized,
        )
        return False

    return True


def _diagnose(elmer, result):
    """Enrich a failed Supabase response with an actionable hint.

    PostgREST's own error bodies are accurate but terse ("Invalid API key");
    this maps the handful of failure modes actually seen in practice to a
    next step, without ever echoing back the configured URL or key.
    """
    message = elmer.type.str.mk(elmer.resolve(result.data, "message"))
    hint = None

    if result.status == 401 or "Invalid API key" in message:
        hint = (
            "Supabase rejected the configured key. Usually this means "
            "SUPABASE_URL and SUPABASE_SERVICE_KEY belong to different "
            "projects, the key was copied with extra whitespace/quotes, or "
            "the Vercel deployment predates a change to those environment "
            "variables (they require a redeploy to take effect)."
        )
    elif result.status == 404:
        hint = (
            "The 'tickets' table was not found. Confirm "
            "supabase/migrations/0001_tickets.sql has been applied to this "
            "project."
        )
    elif result.status == 0:
        hint = "Supabase could not be reached. Check SUPABASE_URL for typos."

    return Obj({"supabase": result.data, "hint": hint}) if hint else result.data


def apply(elmer, router, base_router=None):
    """Define the ticket routes on the passed router."""

    def unavailable(response):
        elmer.app.error.response(
            response,
            Obj({
                "message": "Ticket storage is not configured.",
                "details": ("Set supabase.url and supabase.serviceKey in "
                            "app/config, or the SUPABASE_URL and "
                            "SUPABASE_SERVICE_KEY environment variables."),
            }),
            elmer.io.net.status.serverError.serviceUnavailable,
        )

    # ----------------------------------------------
    # GET /tickets/meta/priorities — the severity ladder, for the web form
    # ----------------------------------------------
    @router.get("/meta/priorities")
    def _priorities(request, response):
        response.status(200).json({
            "priorities": PRIORITIES,
            "statuses": STATUSES,
            "branding": elmer.extend(
                Obj({"name": "CNRZ", "area": "Support"}),
                elmer.resolve(elmer.app.config, "branding"),
            ),
        })

    # ----------------------------------------------
    # POST /tickets/manage/verify — key check for the management forms
    # ----------------------------------------------
    @router.post("/manage/verify")
    def _manage_verify(request, response):
        # _admin_guard writes the 401/503 itself on failure.
        if not _admin_guard(elmer, request, response):
            return
        response.status(200).json({"success": True})

    # ----------------------------------------------
    # POST /tickets — submit a ticket
    # ----------------------------------------------
    @router.post("/")
    def _create(request, response):
        table = _table(elmer)
        if table is None:
            return unavailable(response)

        row, errors = _validate_ticket(elmer, elmer.type.obj.mk(request.body, Obj()))
        if errors:
            return elmer.app.error.response(
                response,
                Obj({"message": "Ticket validation failed.", "details": errors}),
                elmer.io.net.status.clientError.badRequest,
            )

        row.status = "open"
        # Correlate the stored ticket with Elmer's request tracing.
        row.trace_id = elmer.resolve(request.trace, "id")

        result = table.insert(dict(row))
        if not result.ok:
            return elmer.app.error.response(
                response,
                Obj({"message": "Ticket could not be saved.",
                     "details": _diagnose(elmer, result)}),
                elmer.io.net.status.serverError.badGateway,
            )

        ticket = result.data[0] if isinstance(result.data, list) else result.data
        response.status(elmer.io.net.status.success.created).json({
            "success": True,
            "ticket": ticket,
        })

    # ----------------------------------------------
    # GET /tickets — list, filterable by priority/status
    # ----------------------------------------------
    @router.get("/")
    def _list(request, response):
        if not _admin_guard(elmer, request, response):
            return

        table = _table(elmer)
        if table is None:
            return unavailable(response)

        qs = request.querystring
        filters = {}

        priority = elmer.type.str.mk(qs.get("priority")).strip().upper()
        if priority:
            if priority not in PRIORITY_CODES:
                return elmer.app.error.response(
                    response,
                    Obj({"message": "Unknown priority filter.",
                         "details": PRIORITY_CODES}),
                    elmer.io.net.status.clientError.badRequest,
                )
            filters["priority"] = "eq." + priority

        status = elmer.type.str.mk(qs.get("status")).strip().lower()
        if status:
            if status not in STATUSES:
                return elmer.app.error.response(
                    response,
                    Obj({"message": "Unknown status filter.",
                         "details": STATUSES}),
                    elmer.io.net.status.clientError.badRequest,
                )
            filters["status"] = "eq." + status

        # Company/email are substring, case-insensitive matches (PostgREST's
        # ilike with wildcards either side) rather than exact — e.g.
        # email=@gmail.com should match every @gmail.com address.
        company = elmer.type.str.mk(qs.get("company")).strip()
        if company:
            filters["company"] = "ilike.*" + company + "*"

        email = elmer.type.str.mk(qs.get("email")).strip()
        if email:
            filters["email"] = "ilike.*" + email + "*"

        limit = min(max(elmer.type.int.mk(qs.get("limit"), 50), 1), 200)
        offset = max(elmer.type.int.mk(qs.get("offset"), 0), 0)

        result = table.select(filters, order="created_at.desc",
                              limit=limit, offset=offset)
        if not result.ok:
            return elmer.app.error.response(
                response,
                Obj({"message": "Tickets could not be read.",
                     "details": _diagnose(elmer, result)}),
                elmer.io.net.status.serverError.badGateway,
            )

        response.status(200).json({
            "success": True,
            "count": len(result.data or []),
            "tickets": result.data or [],
        })

    # ----------------------------------------------
    # GET /tickets/:id — read one ticket
    # ----------------------------------------------
    @router.get("/:id")
    def _read(request, response):
        if not _admin_guard(elmer, request, response):
            return

        table = _table(elmer)
        if table is None:
            return unavailable(response)

        ticket_id = elmer.type.str.mk(request.params.get("id")).strip()
        if not _UUID_RE.match(ticket_id):
            return elmer.app.error.response(
                response, "Ticket id must be a UUID.",
                elmer.io.net.status.clientError.badRequest,
            )

        result = table.select({"id": "eq." + ticket_id}, limit=1)
        if not result.ok:
            return elmer.app.error.response(
                response,
                Obj({"message": "Ticket could not be read.",
                     "details": _diagnose(elmer, result)}),
                elmer.io.net.status.serverError.badGateway,
            )

        rows = result.data or []
        if not rows:
            return elmer.app.error.response(
                response, "Ticket not found.",
                elmer.io.net.status.clientError.notFound,
            )

        payload = Obj({"success": True, "ticket": rows[0], "updates": []})

        # Status history, newest first. A history-read failure degrades to
        # an empty list with a flag rather than failing the whole read.
        history = _table(elmer, "ticket_status_updates")
        if history is not None:
            updates = history.select({"ticket_id": "eq." + ticket_id},
                                     order="created_at.desc")
            if updates.ok:
                payload.updates = updates.data or []
            else:
                payload.updates_error = True

        response.status(200).json(payload)

    # ----------------------------------------------
    # POST /tickets/:id/status — advance a ticket's lifecycle
    # ----------------------------------------------
    @router.post("/:id/status")
    def _set_status(request, response):
        if not _admin_guard(elmer, request, response):
            return

        table = _table(elmer)
        if table is None:
            return unavailable(response)

        ticket_id = elmer.type.str.mk(request.params.get("id")).strip()
        if not _UUID_RE.match(ticket_id):
            return elmer.app.error.response(
                response, "Ticket id must be a UUID.",
                elmer.io.net.status.clientError.badRequest,
            )

        status = elmer.type.str.mk(
            elmer.resolve(request.body, "status")).strip().lower()
        if status not in STATUSES:
            return elmer.app.error.response(
                response,
                Obj({"message": "Unknown status.", "details": STATUSES}),
                elmer.io.net.status.clientError.badRequest,
            )

        message = elmer.type.str.mk(
            elmer.resolve(request.body, "message")).strip()
        if len(message) > 2000:
            return elmer.app.error.response(
                response, "'message' must be 2000 characters or fewer.",
                elmer.io.net.status.clientError.badRequest,
            )

        result = table.update({"id": "eq." + ticket_id}, {"status": status})
        if not result.ok:
            return elmer.app.error.response(
                response,
                Obj({"message": "Ticket could not be updated.",
                     "details": _diagnose(elmer, result)}),
                elmer.io.net.status.serverError.badGateway,
            )

        rows = result.data or []
        if not rows:
            return elmer.app.error.response(
                response, "Ticket not found.",
                elmer.io.net.status.clientError.notFound,
            )

        payload = Obj({"success": True, "ticket": rows[0], "update": None})

        # Record the change (and its message) in the history table. The
        # status change itself has already succeeded, so a history-write
        # failure is reported alongside rather than turned into an error —
        # otherwise a retry would double-apply nothing but still confuse.
        history = _table(elmer, "ticket_status_updates")
        if history is not None:
            record = history.insert({
                "ticket_id": ticket_id,
                "status": status,
                "message": message or None,
            })
            if record.ok:
                entries = record.data or []
                payload.update = entries[0] if entries else None
            else:
                payload.history_error = True

        response.status(200).json(payload)

    # ----------------------------------------------
    # GET /tickets/:id/public — read-only status view, NO admin key
    # ----------------------------------------------
    # The unguessable ticket UUID acts as the access token (the submitter
    # receives it at creation), so this endpoint deliberately returns a
    # REDUCED shape: subject, priority, lifecycle, timestamps, and the
    # status history. Reporter identity (name, email, company) and the
    # full description are withheld — anyone who is handed the link can
    # follow progress without being handed the reporter's details.
    @router.get("/:id/public")
    def _public_read(request, response):
        table = _table(elmer)
        if table is None:
            return unavailable(response)

        ticket_id = elmer.type.str.mk(request.params.get("id")).strip()
        if not _UUID_RE.match(ticket_id):
            return elmer.app.error.response(
                response, "Ticket id must be a UUID.",
                elmer.io.net.status.clientError.badRequest,
            )

        result = table.select({"id": "eq." + ticket_id}, limit=1)
        if not result.ok:
            return elmer.app.error.response(
                response,
                Obj({"message": "Ticket could not be read.",
                     "details": _diagnose(elmer, result)}),
                elmer.io.net.status.serverError.badGateway,
            )

        rows = result.data or []
        if not rows:
            return elmer.app.error.response(
                response, "Ticket not found.",
                elmer.io.net.status.clientError.notFound,
            )

        ticket = rows[0]
        updates = []
        history = _table(elmer, "ticket_status_updates")
        if history is not None:
            fetched = history.select({"ticket_id": "eq." + ticket_id},
                                     order="created_at.desc")
            if fetched.ok:
                updates = [
                    {"status": u.get("status"),
                     "message": u.get("message"),
                     "created_at": u.get("created_at")}
                    for u in (fetched.data or [])
                ]

        response.status(200).json({
            "success": True,
            "ticket": {
                "id": ticket.get("id"),
                "subject": ticket.get("subject"),
                "priority": ticket.get("priority"),
                "status": ticket.get("status"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at"),
            },
            "updates": updates,
        })
