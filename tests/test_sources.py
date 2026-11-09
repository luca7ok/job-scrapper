import json
from datetime import date
from pathlib import Path

import pytest

from tracker import config
from tracker.sources import ATS, arbeitnow, earlycareers_eu, manual, simplify, speedyapply

FIX = Path(__file__).parent / "fixtures"


def load(name):
    text = (FIX / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


@pytest.mark.parametrize("feed", ["simplify_intern", "simplify_newgrad"])
def test_simplify(feed):
    posts = simplify.parse(load(f"{feed}.json"), feed)
    assert len(posts) > 50
    p = posts[0]
    assert p.company and p.title and p.url.startswith("http") and p.locations
    assert all(not p.posted or p.posted >= simplify.MIN_POSTED for p in posts)


def test_simplify_drops_old_terms_and_inactive():
    raw = [
        {"company_name": "A", "title": "SWE Intern", "active": True, "is_visible": True, "terms": ["Summer 2026"], "date_posted": 1794219187, "url": "https://a", "locations": ["Berlin, Germany"]},
        {"company_name": "B", "title": "SWE Intern", "active": False, "is_visible": True, "terms": ["Summer 2027"], "date_posted": 1794219187, "url": "https://b", "locations": ["Berlin, Germany"]},
        {"company_name": "C", "title": "SWE Intern", "active": True, "is_visible": True, "terms": ["Summer 2027"], "date_posted": 1700000000, "url": "https://c", "locations": ["Berlin, Germany"]},
        {"company_name": "D", "title": "SWE Intern", "active": True, "is_visible": True, "terms": ["Summer 2026", "Summer 2027"], "date_posted": 1794219187, "url": "https://d", "locations": ["Berlin, Germany"]},
    ]
    assert [p.company for p in simplify.parse(raw, "simplify_intern")] == ["D"]


@pytest.mark.parametrize("feed", ["speedyapply_intern", "speedyapply_newgrad"])
def test_speedyapply(feed):
    posts = speedyapply.parse(load(f"{feed}.md"), feed, today=date(2026, 11, 9))
    assert len(posts) > 100
    p = posts[0]
    assert p.company and "<" not in p.company
    assert p.url.startswith("http")
    assert p.posted and p.posted <= "2026-11-09"


def test_earlycareers():
    posts = earlycareers_eu.parse(load("earlycareers.md"))
    assert len(posts) > 50
    kinds = {p.kind_hint for p in posts}
    assert "Internship" in kinds
    assert all(p.url.startswith("http") for p in posts)
    assert all(p.company[:1].isupper() or not p.company[:1].isalpha() for p in posts)


def test_arbeitnow():
    posts = arbeitnow.parse(load("arbeitnow.json"))
    assert posts and all(p.url.startswith("http") for p in posts)


def test_manual_entries_from_config():
    cfg = config.load()
    posts = manual.parse(cfg.manual_entries)
    assert len(posts) == len(cfg.manual_entries) == 44
    booking = next(p for p in posts if p.company == "Booking.com")
    assert booking.countries == ["NL"] and booking.start_hint == "July 2027"
    assert sum(1 for p in posts if p.status == "expected") == 14


def _ats_fixtures():
    return sorted(p.name for p in FIX.glob("*__*.json"))


@pytest.mark.parametrize("name", _ats_fixtures())
def test_ats_fixture_parses(name):
    ats, slug = name[:-5].split("__", 1)
    cfg = config.load()
    entry = next(e for e in cfg.ats_companies if e["ats"] == ats and e["slug"].replace("|", "_") == slug)
    mod = ATS[ats]
    kwargs = {"today": date(2026, 11, 9)} if ats == "workday" else {}
    posts = mod.parse(load(name), entry, **kwargs)
    assert posts, name
    for p in posts:
        assert p.company == entry["company"]
        assert p.title
        assert p.url.startswith("https://")
        assert p.source == ats


def test_every_ats_has_two_fixtures():
    names = _ats_fixtures()
    for ats in ATS:
        assert sum(1 for n in names if n.startswith(ats + "__")) >= 2, ats


def test_adzuna_parse_and_missing_key(monkeypatch):
    from tracker.sources import adzuna
    raw = {"results": [
        {"title": "Junior <strong>Software</strong> Developer (m/w/d)", "company": {"display_name": "Acme GmbH"},
         "location": {"display_name": "Berlin, Deutschland", "area": ["Deutschland", "Berlin"]},
         "redirect_url": "https://www.adzuna.de/land/ad/123", "created": "2026-11-01T10:00:00Z",
         "description": "Start: Juli 2027 in Berlin", "_cc": "de"},
        {"title": "Software Engineer Intern", "company": {"display_name": "Bloomberg"},
         "location": {"display_name": "London, UK"}, "redirect_url": "https://www.adzuna.co.uk/land/ad/9",
         "created": "2026-10-20T10:00:00Z", "description": "", "_cc": "gb"},
    ]}
    posts = adzuna.parse(raw)
    assert posts[0].title == "Junior Software Developer (m/w/d)"
    assert posts[0].countries == ["DE"] and posts[0].posted == "2026-11-01"
    assert posts[1].countries == ["GB"]
    monkeypatch.delenv("ADZUNA_ID", raising=False)
    monkeypatch.delenv("ADZUNA_KEY", raising=False)
    with pytest.raises(adzuna.MissingKey):
        adzuna.fetch_raw("adzuna", None)
