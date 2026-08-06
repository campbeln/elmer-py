"""Ticket API: validation, CRUD via FakeTable, the admin guard, diagnostics."""

import json
import os

from _helpers import (ADMIN_KEY, BAD_HEADERS, FakeTable, GOOD_HEADERS,
                      UnauthorizedTable, get_app, make_ticket, run_module,
                      use_table)


def _json(response):
    return json.loads(response.get_data(as_text=True))


def test_meta_serves_ladder_and_branding():
    _, _, client = get_app()
    data = _json(client.get("/tickets/meta/priorities"))
    assert [p["code"] for p in data["priorities"]] == ["P1", "P2", "P3", "P4"]
    assert data["statuses"][0] == "open"
    assert data["branding"]["name"]      # config-driven wordmark


def test_unconfigured_storage_returns_503():
    _, _, client = get_app()
    previous = use_table(None)
    try:
        status, data = make_ticket(client)
        assert status == 503
        assert "not configured" in data["error"]
    finally:
        use_table(previous)


def test_validation_rejects_bad_input():
    _, _, client = get_app()
    previous = use_table(FakeTable())
    try:
        status, data = make_ticket(client, email="not-an-email")
        assert status == 400 and "email" in " ".join(data["details"])

        status, data = make_ticket(client, priority="P9")
        assert status == 400 and "P1, P2, P3, P4" in " ".join(data["details"])

        response = client.post("/tickets/", json={"name": "Only Name"})
        assert response.status_code == 400
    finally:
        use_table(previous)


def test_crud_flow_with_guard():
    _, _, client = get_app()
    previous = use_table(FakeTable())
    try:
        # Create is public; priority is normalised to upper case.
        status, data = make_ticket(client, priority="p1")
        assert status == 201
        ticket = data["ticket"]
        assert ticket["priority"] == "P1"
        assert ticket["trace_id"], "tickets must carry the request trace id"

        # Management endpoints require the key…
        assert client.get("/tickets/").status_code == 401
        assert client.get("/tickets/", headers=BAD_HEADERS).status_code == 401

        # …and work with it.
        listing = _json(client.get("/tickets/?priority=P1",
                                   headers=GOOD_HEADERS))
        assert listing["count"] == 1

        read = _json(client.get("/tickets/" + ticket["id"],
                                headers=GOOD_HEADERS))
        assert read["ticket"]["subject"] == "Test ticket"

        updated = _json(client.post("/tickets/%s/status" % ticket["id"],
                                    json={"status": "resolved"},
                                    headers=GOOD_HEADERS))
        assert updated["ticket"]["status"] == "resolved"

        bogus = client.post("/tickets/%s/status" % ticket["id"],
                            json={"status": "bogus"}, headers=GOOD_HEADERS)
        assert bogus.status_code == 400

        bad_uuid = client.get("/tickets/not-a-uuid", headers=GOOD_HEADERS)
        assert bad_uuid.status_code == 400
    finally:
        use_table(previous)


def test_manage_verify_endpoint():
    _, _, client = get_app()
    assert client.post("/tickets/manage/verify",
                       headers=GOOD_HEADERS).status_code == 200
    assert client.post("/tickets/manage/verify",
                       headers=BAD_HEADERS).status_code == 401
    assert client.post("/tickets/manage/verify").status_code == 401


def test_guard_fails_closed_when_key_unset():
    _, _, client = get_app()
    saved = os.environ.pop("TICKETS_ADMIN_KEY", None)
    try:
        response = client.get("/tickets/", headers=GOOD_HEADERS)
        assert response.status_code == 503
        assert "not enabled" in _json(response)["error"]
    finally:
        if saved is not None:
            os.environ["TICKETS_ADMIN_KEY"] = saved


def test_supabase_auth_failure_gets_actionable_hint():
    _, _, client = get_app()
    previous = use_table(UnauthorizedTable())
    try:
        response = client.get("/tickets/", headers=GOOD_HEADERS)
        assert response.status_code == 502
        details = _json(response)["details"]
        assert details["supabase"]["message"] == "Invalid API key"
        assert "redeploy" in details["hint"]   # points at the usual Vercel cause

        # An auth failure must never masquerade as "not found".
        read = client.get(
            "/tickets/00000000-0000-0000-0000-000000000000",
            headers=GOOD_HEADERS)
        assert read.status_code == 502, "must be 502 (upstream), not 404"
    finally:
        use_table(previous)


def test_status_message_recorded_and_history_returned():
    _, _, client = get_app()
    prev_tickets = use_table(FakeTable())
    prev_updates = use_table(FakeTable(), "ticket_status_updates")
    try:
        _, data = make_ticket(client)
        ticket_id = data["ticket"]["id"]

        # Two status changes, each with a message.
        first = _json(client.post("/tickets/%s/status" % ticket_id,
                                  json={"status": "acknowledged",
                                        "message": "We're on it."},
                                  headers=GOOD_HEADERS))
        assert first["update"]["message"] == "We're on it."

        second = _json(client.post("/tickets/%s/status" % ticket_id,
                                   json={"status": "resolved",
                                         "message": "Root cause fixed."},
                                   headers=GOOD_HEADERS))
        assert second["update"]["status"] == "resolved"

        # Message length ceiling mirrors the DB constraint.
        too_long = client.post("/tickets/%s/status" % ticket_id,
                               json={"status": "closed", "message": "x" * 2001},
                               headers=GOOD_HEADERS)
        assert too_long.status_code == 400

        # Management read includes the history, newest first.
        read = _json(client.get("/tickets/" + ticket_id, headers=GOOD_HEADERS))
        messages = [u["message"] for u in read["updates"]]
        assert messages == ["Root cause fixed.", "We're on it."]
    finally:
        use_table(prev_tickets)
        use_table(prev_updates, "ticket_status_updates")


def test_public_endpoint_needs_no_key_and_limits_fields():
    _, _, client = get_app()
    prev_tickets = use_table(FakeTable())
    prev_updates = use_table(FakeTable(), "ticket_status_updates")
    try:
        _, data = make_ticket(client, email="private@example.com")
        ticket_id = data["ticket"]["id"]
        client.post("/tickets/%s/status" % ticket_id,
                    json={"status": "in_progress", "message": "Digging in."},
                    headers=GOOD_HEADERS)

        # No X-Admin-Key on this request — and none needed.
        response = client.get("/tickets/%s/public" % ticket_id)
        assert response.status_code == 200
        payload = _json(response)

        # Status history present, newest first.
        assert payload["updates"][0]["message"] == "Digging in."

        # Reporter identity and description are withheld: the UUID link is
        # shareable, so it must not hand out PII.
        body = response.get_data(as_text=True)
        assert "private@example.com" not in body
        for field in ("name", "email", "company", "description"):
            assert field not in payload["ticket"], field

        assert client.get("/tickets/%s/public"
                          % "00000000-0000-0000-0000-000000000000"
                          ).status_code == 404
        assert client.get("/tickets/not-a-uuid/public").status_code == 400
    finally:
        use_table(prev_tickets)
        use_table(prev_updates, "ticket_status_updates")


def test_list_filters_by_email_and_company_substring():
    _, _, client = get_app()
    prev_tickets = use_table(FakeTable())
    try:
        make_ticket(client, email="ada@analyticalengines.com",
                   company="Analytical Engines")
        make_ticket(client, email="bob@gmail.com", company="")
        make_ticket(client, email="carol@gmail.com", company="Acme Corp")

        by_email = _json(client.get("/tickets/?email=@gmail.com",
                                    headers=GOOD_HEADERS))
        assert by_email["count"] == 2
        assert all("@gmail.com" in t["email"] for t in by_email["tickets"])

        # Case-insensitive, partial match.
        by_company = _json(client.get("/tickets/?company=acme",
                                      headers=GOOD_HEADERS))
        assert by_company["count"] == 1
        assert by_company["tickets"][0]["company"] == "Acme Corp"

        # Combined with an existing exact filter.
        combined = _json(client.get(
            "/tickets/?priority=P3&email=analyticalengines",
            headers=GOOD_HEADERS))
        assert combined["count"] == 1
    finally:
        use_table(prev_tickets)


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
