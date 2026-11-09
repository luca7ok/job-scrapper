import json
import shutil
from pathlib import Path

from tracker import config
from tracker.schema import norm_company
from tracker.update import main

FIX = Path(__file__).parent / "fixtures"


def offline(tmp: Path, fixtures: Path, day: str):
    rc = main(["--offline", "--fixtures", str(fixtures), "--data-dir", str(tmp / "data"), "--site-dir", str(tmp / "site"), "--today", day])
    assert rc == 0
    return json.loads((tmp / "site" / "data" / "roles.json").read_text())


def test_offline_run_produces_site_data(tmp_path):
    out = offline(tmp_path, FIX, "2026-11-09")
    assert out["stats"]["roles"] > 300
    assert out["stats"]["outside_uk"] > 150
    assert {"generated_at", "stats", "watchlist", "roles"} <= set(out)
    assert (tmp_path / "data" / "state.json").exists()
    assert (tmp_path / "data" / "run_report.md").exists()
    assert not (tmp_path / "data" / "notify.md").exists()
    for r in out["roles"]:
        assert r["countries"] or r["source"] == "manual"
        assert r["start_bucket"] in {"july", "summer", "other", "none"}
        assert r["kind"] in {"Internship", "New grad", "PhD / research"}


def test_all_manual_entries_present(tmp_path):
    out = offline(tmp_path, FIX, "2026-11-09")
    cfg = config.load()
    present = {(norm_company(r["company"]), r["title"]) for r in out["roles"]}
    for m in cfg.manual_entries:
        assert (norm_company(m["company"]), m["title"]) in present, m["title"]
    expected = [r for r in out["roles"] if r["status"] == "expected"]
    assert len(expected) == 14


def test_removed_role_closes_after_two_runs(tmp_path):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIX, fixtures)
    first = offline(tmp_path, fixtures, "2026-11-09")
    target = next(r for r in first["roles"] if r["source"] == "lever" and r["sources"] == ["lever"])

    path = next(fixtures.glob("lever__*.json"))
    for p in fixtures.glob("lever__*.json"):
        raw = json.loads(p.read_text())
        if any(x.get("hostedUrl") == target["url"] for x in raw["postings"]):
            path = p
            break
    raw = json.loads(path.read_text())
    raw["postings"] = [x for x in raw["postings"] if x.get("hostedUrl") != target["url"]]
    path.write_text(json.dumps(raw))

    second = offline(tmp_path, fixtures, "2026-11-10")
    r2 = next(r for r in second["roles"] if r["id"] == target["id"])
    assert r2["status"] == "open"

    third = offline(tmp_path, fixtures, "2026-11-11")
    r3 = next(r for r in third["roles"] if r["id"] == target["id"])
    assert r3["status"] == "closed"
    assert r3["closed_on"] == "2026-11-11"


def test_new_role_triggers_notification(tmp_path):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIX, fixtures)
    offline(tmp_path, fixtures, "2026-11-09")
    path = fixtures / "simplify_intern.json"
    raw = json.loads(path.read_text())
    raw.append({
        "company_name": "Brand New Co", "title": "Software Engineer Intern (Summer 2027)", "active": True,
        "is_visible": True, "terms": ["Summer 2027"], "date_posted": 1794219187,
        "url": "https://example.com/brand-new", "locations": ["Berlin, Germany"],
    })
    path.write_text(json.dumps(raw))
    out = offline(tmp_path, fixtures, "2026-11-10")
    new = [r for r in out["roles"] if r["is_new"]]
    assert [r["company"] for r in new] == ["Brand New Co"]
    body = (tmp_path / "data" / "notify.md").read_text()
    assert "Brand New Co" in body


def test_default_view_has_uk_only_roles_flagged(tmp_path):
    out = offline(tmp_path, FIX, "2026-11-09")
    uk_only = [r for r in out["roles"] if r["countries"] == ["GB"]]
    assert uk_only
    non_uk = [r for r in out["roles"] if any(c != "GB" for c in r["countries"])]
    assert len(non_uk) == out["stats"]["outside_uk"] + sum(1 for r in non_uk if r["status"] != "open")


def test_ntfy_summary_and_push(monkeypatch):
    from tracker import notify
    line = notify.summary_line(3, [{"company": "Bolt", "role_ids": ["x"]}], 1)
    assert line == "🔔 Bolt opened · 3 new roles · 1 July start"

    sent = {}

    class FakeResp:
        status_code = 200

    class FakeHttp:
        def post(self, url, content=None, headers=None):
            sent.update(url=url, body=content.decode(), headers=headers)
            return FakeResp()

    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    assert notify.push_ntfy(FakeHttp(), line) is False
    monkeypatch.setenv("NTFY_TOPIC", "my-topic")
    assert notify.push_ntfy(FakeHttp(), line) is True
    assert sent["url"] == "https://ntfy.sh/my-topic" and sent["body"] == line
    assert sent["headers"]["Click"].startswith("https://luca7ok.github.io/")
