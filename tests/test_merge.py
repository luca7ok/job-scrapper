from datetime import date, timedelta

from tracker.merge import FeedStatus, dedupe, merge_state
from tracker.schema import Role

D0 = date(2026, 11, 9)


def role(rid, company="Acme", title="Software Engineer Intern", source="greenhouse", feed="greenhouse:acme", countries=("NL",), **kw):
    base = dict(
        id=rid, company=company, title=title, kind="Internship", countries=list(countries),
        locations="Amsterdam", start_label="Not stated", start_month=None, start_bucket="none",
        url=f"https://example.com/{rid}", source=source, midsize=False, posted=None,
        first_seen="", last_seen="", status="open", is_new=False, note="",
        sources=[source], feeds=[feed],
    )
    base.update(kw)
    return Role(**base)


def run(state, roles, feeds, day, watch=frozenset()):
    return merge_state(state, roles, feeds, day, set(watch))


def ok(n):
    return FeedStatus(ok=True, count=n)


def test_closed_only_after_two_missing_runs():
    a, b = role("a"), role("b", title="Backend Intern")
    r = run({}, [a, b], {"greenhouse:acme": ok(2)}, D0)
    assert r.bootstrap and not r.new_ids
    r = run(r.state, [a], {"greenhouse:acme": ok(1)}, D0 + timedelta(days=1))
    assert r.state["roles"]["b"]["status"] == "open"
    assert r.state["roles"]["b"]["missing_runs"] == 1
    r = run(r.state, [a], {"greenhouse:acme": ok(1)}, D0 + timedelta(days=2))
    assert r.state["roles"]["b"]["status"] == "closed"
    assert r.closed_ids == ["b"]


def test_reappearing_resets_missing_counter():
    a, b = role("a"), role("b", title="Backend Intern")
    r = run({}, [a, b], {"greenhouse:acme": ok(2)}, D0)
    r = run(r.state, [a], {"greenhouse:acme": ok(1)}, D0 + timedelta(days=1))
    r = run(r.state, [a, b], {"greenhouse:acme": ok(2)}, D0 + timedelta(days=2))
    r = run(r.state, [a], {"greenhouse:acme": ok(1)}, D0 + timedelta(days=3))
    assert r.state["roles"]["b"]["status"] == "open"


def test_outage_protection():
    a = role("a")
    r = run({}, [a], {"greenhouse:acme": ok(1)}, D0)
    for i in range(1, 4):
        r = run(r.state, [], {"greenhouse:acme": ok(0)}, D0 + timedelta(days=i))
        assert r.outages == ["greenhouse:acme"]
        assert r.state["roles"]["a"]["status"] == "open"
        assert r.state["roles"]["a"].get("missing_runs", 0) == 0


def test_failed_feed_does_not_close():
    a = role("a")
    r = run({}, [a], {"greenhouse:acme": ok(1)}, D0)
    for i in range(1, 4):
        r = run(r.state, [], {"greenhouse:acme": FeedStatus(ok=False, count=0, error="boom")}, D0 + timedelta(days=i))
    assert r.state["roles"]["a"]["status"] == "open"


def test_skipped_feed_does_not_close():
    a = role("a")
    r = run({}, [a], {"greenhouse:acme": ok(1)}, D0)
    for i in range(1, 4):
        r = run(r.state, [], {"greenhouse:acme": FeedStatus(ok=False, count=0, skipped=True)}, D0 + timedelta(days=i))
    assert r.state["roles"]["a"]["status"] == "open"


def test_dedupe_priority_manual_over_ats_over_lists():
    m = role("m", source="manual", feed="manual", note="from research", start_label="July 2027", start_month=7, start_bucket="july")
    g = role("g", source="greenhouse")
    s = role("s", source="simplify", feed="simplify_intern")
    e = role("e", source="earlycareers", feed="earlycareers")
    out, aliases = dedupe([e, s, g, m])
    assert len(out) == 1
    assert out[0].source == "manual"
    assert out[0].id == "m"
    assert set(out[0].sources) == {"manual", "greenhouse", "simplify", "earlycareers"}
    assert out[0].start_bucket == "july"


def test_dedupe_keeps_richest_start():
    g = role("g", source="greenhouse")
    s = role("s", source="simplify", feed="simplify_intern", start_label="Summer 2027", start_bucket="summer")
    out, _ = dedupe([g, s])
    assert out[0].source == "greenhouse"
    assert out[0].start_label == "Summer 2027"


def test_dedupe_ats_beats_simplify_beats_speedyapply():
    s = role("s", source="simplify", feed="simplify_intern")
    sp = role("sp", source="speedyapply", feed="speedyapply_intern")
    out, _ = dedupe([sp, s])
    assert out[0].source == "simplify"


def test_fuzzy_dedupe_needs_same_country():
    a = role("a", countries=("NL",))
    b = role("b", countries=("DE",), source="simplify")
    out, _ = dedupe([a, b])
    assert len(out) == 2


def test_fuzzy_dedupe_window():
    a = role("a", posted="2026-11-01")
    b = role("b", posted="2026-08-01", source="simplify")
    out, _ = dedupe([a, b])
    assert len(out) == 2


def test_fuzzy_match_against_state():
    a = role("a", source="simplify", feed="simplify_intern")
    r = run({}, [a], {"simplify_intern": ok(1)}, D0)
    b = role("b", source="greenhouse")
    r = run(r.state, [b], {"simplify_intern": ok(0), "greenhouse:acme": ok(1)}, D0 + timedelta(days=1))
    assert "b" not in r.state["roles"]
    assert r.state["roles"]["a"]["source"] == "greenhouse"
    assert not r.new_ids


def test_new_flag_and_watchlist_hit():
    a = role("a")
    r = run({}, [a], {"greenhouse:acme": ok(1)}, D0)
    assert r.state["roles"]["a"]["is_new"] is False
    w = role("w", company="Bolt", title="Software Engineering Intern", feed="manual", source="manual")
    r = run(r.state, [a, w], {"greenhouse:acme": ok(1), "manual": ok(1)}, D0 + timedelta(days=1), watch={"bolt"})
    assert r.new_ids == ["w"]
    assert r.state["roles"]["w"]["is_new"] is True
    assert r.hits and r.hits[0]["company"] == "Bolt"


def test_no_hit_when_company_already_open():
    w1 = role("w1", company="Bolt", feed="manual", source="manual")
    r = run({}, [w1], {"manual": ok(1)}, D0)
    w2 = role("w2", company="Bolt", title="Backend Intern", feed="manual", source="manual")
    r = run(r.state, [w1, w2], {"manual": ok(2)}, D0 + timedelta(days=1), watch={"bolt"})
    assert r.new_ids == ["w2"]
    assert not r.hits
