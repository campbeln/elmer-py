"""Spot checks on the ported ish type library the whole app is built on."""

from _helpers import get_app, run_module


def test_type_coercions():
    elmer, _, _ = get_app()
    t = elmer.type
    assert t.str.cmp(" JWT ", ["basic", "jwt"]) is True
    assert t.bool.mk("true", False) is True
    assert t.bool.mk("nonsense", False) is False
    assert t.int.mk("42", 0) == 42
    assert t.int.mk("junk", 7) == 7
    assert t.obj.mk('{"a": 1}')["a"] == 1


def test_resolve_and_extend():
    elmer, _, _ = get_app()
    assert elmer.resolve({"a": {"b": {"c": 42}}}, "a.b.c") == 42
    assert elmer.resolve({}, "missing.path", "fallback") == "fallback"
    merged = elmer.extend({"a": {"x": 1}}, {"a": {"y": 2}})
    assert merged["a"] == {"x": 1, "y": 2}


def test_query_nested_criteria():
    elmer, _, _ = get_app()
    rows = [{"trace": {"id": "x"}}, {"trace": {"id": "y"}}]
    hits = elmer.type.query(rows, {"trace": {"id": "y"}})
    assert len(hits) == 1 and hits[0]["trace"]["id"] == "y"
    first = elmer.type.query(rows, {"trace": {"id": "x"}},
                             {"firstEntryOnly": True})
    assert first["trace"]["id"] == "x"


def test_date_helpers():
    elmer, _, _ = get_app()
    import re
    from datetime import datetime
    # format(0, ...) renders the local epoch date, so compute the expectation
    # the same way rather than hard-coding a timezone-dependent string.
    expected = datetime.fromtimestamp(0).strftime("%Y-%m-%d")
    assert elmer.type.date.format(0, "YYYY-MM-DD") == expected
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", expected)
    # Small numbers are treated as SECONDS (matching the JS heuristic):
    # 90061 s = 1 day, 1 hour, 1 minute, 1 second.
    assert elmer.type.date.ydhms(0, 90061) == "1d 1h 1m 1s"
    assert elmer.type.uuid().count("-") == 4


if __name__ == "__main__":
    raise SystemExit(run_module(globals()))
