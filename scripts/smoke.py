from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracker import config as cfgmod  # noqa: E402
from tracker.filters import FilterSet  # noqa: E402
from tracker.geo import europe_countries  # noqa: E402
from tracker.http import client  # noqa: E402
from tracker.sources import AGGREGATORS, ATS, LISTS  # noqa: E402
from tracker.sources import adzuna, workday  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
FIXTURES_PER_ATS = 2
MAX_ITEMS = 250


def safe(slug: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", slug)


def probe(entry: dict) -> tuple[dict, int, str]:
    http = client()
    ats, slug = entry["ats"], entry["slug"]
    try:
        if ats == "greenhouse":
            for host in ("https://boards-api.greenhouse.io", "https://boards-api.eu.greenhouse.io"):
                r = http.get(f"{host}/v1/boards/{slug}/jobs")
                if r.status_code == 200:
                    return entry, 200, f"{len(r.json().get('jobs', []))} jobs ({host.split('//')[1]})"
            return entry, r.status_code, "not found on US or EU host"
        if ats == "lever":
            for host in ("https://api.lever.co", "https://api.eu.lever.co"):
                r = http.get(f"{host}/v0/postings/{slug}?mode=json&limit=1")
                if r.status_code == 200:
                    return entry, 200, f"ok ({host.split('//')[1]})"
            return entry, r.status_code, "not found on US or EU host"
        if ats == "ashby":
            r = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            n = len(r.json().get("jobs", [])) if r.status_code == 200 else 0
            return entry, r.status_code, f"{n} jobs"
        if ats == "workable":
            r = http.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
            n = len(r.json().get("jobs", [])) if r.status_code == 200 else 0
            return entry, r.status_code, f"{n} jobs"
        if ats == "smartrecruiters":
            r = http.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1")
            n = r.json().get("totalFound", 0) if r.status_code == 200 else 0
            code = r.status_code if n or r.status_code != 200 else 204
            return entry, code, f"{n} postings"
        if ats == "workday":
            r = http.post(workday.base(slug) + "/jobs", json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": "intern"})
            n = r.json().get("total", 0) if r.status_code == 200 else 0
            return entry, r.status_code, f"{n} hits for 'intern'"
        return entry, 0, f"unknown ats {ats}"
    except Exception as exc:
        return entry, -1, f"{type(exc).__name__}: {exc}"


def trim_list(items: list, keep) -> list:
    keepers = [x for x in items if keep(x)]
    others = [x for x in items if not keep(x)][: max(0, MAX_ITEMS - len(keepers)) // 4]
    return keepers + others


def save(name: str, data) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def trim_ats(ats: str, raw: dict, fs: FilterSet) -> dict:
    def title_ok(t: str) -> bool:
        return fs.is_swe(t) or bool(fs.kind(t))
    if ats == "greenhouse":
        raw["jobs"] = trim_list(raw.get("jobs", []), lambda j: title_ok(j.get("title", "")))
    elif ats == "lever":
        raw["postings"] = trim_list(raw.get("postings", []), lambda j: title_ok(j.get("text", "")))
    elif ats in ("ashby", "workable"):
        raw["jobs"] = trim_list(raw.get("jobs", []), lambda j: title_ok(j.get("title", "")))
    elif ats == "smartrecruiters":
        raw["content"] = trim_list(raw.get("content", []), lambda j: title_ok(j.get("name", "")))
    elif ats == "workday":
        raw["jobPostings"] = trim_list(raw.get("jobPostings", []), lambda j: title_ok(j.get("title", "")))
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fixtures", action="store_true")
    ap.add_argument("--ats", default=None)
    args = ap.parse_args()

    cfg = cfgmod.load()
    fs = FilterSet.from_config(cfg.filters)
    http = client()
    report: dict = {"lists": {}, "ats": [], "aggregators": {}}

    print("== GitHub lists")
    for feed, mod in LISTS.items():
        try:
            raw = mod.fetch_raw(feed, http)
            size = len(raw) if isinstance(raw, (list, str)) else 0
            print(f"  200  {feed:22} {size}")
            report["lists"][feed] = {"status": 200, "size": size}
            if not args.no_fixtures:
                if feed.startswith("simplify"):
                    eu = lambda x: x.get("active") and bool(europe_countries("; ".join(x.get("locations") or [])))
                    save(f"{feed}.json", trim_list(raw, eu))
                else:
                    save(f"{feed}.md", raw)
        except Exception as exc:
            print(f"  ERR  {feed:22} {exc}")
            report["lists"][feed] = {"status": -1, "error": str(exc)}

    print("== Aggregators")
    for feed, mod in AGGREGATORS.items():
        try:
            if feed == "adzuna":
                if adzuna.credentials() is None:
                    print("  SKIP adzuna (ADZUNA_ID / ADZUNA_KEY not set)")
                    report["aggregators"][feed] = {"status": "skipped"}
                    continue
                raw = mod.fetch_raw(feed, http, countries=["de", "nl"])
                for r in raw.get("results", []):
                    r.pop("adref", None)
            else:
                raw = mod.fetch_raw(feed, http, max_pages=1)
            n = len(raw.get("data") or raw.get("results") or [])
            print(f"  200  {feed:22} {n}")
            report["aggregators"][feed] = {"status": 200, "size": n}
            if not args.no_fixtures:
                key = "data" if "data" in raw else "results"
                raw[key] = trim_list(raw[key], lambda j: fs.is_swe(j.get("title", "")) or bool(fs.kind(j.get("title", ""))))
                save(f"{feed}.json", raw)
        except Exception as exc:
            print(f"  ERR  {feed:22} {exc}")
            report["aggregators"][feed] = {"status": -1, "error": str(exc)}

    entries = [e for e in cfg.ats_companies if not args.ats or e["ats"] == args.ats]
    print(f"== ATS slugs ({len(entries)})")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, entries))
    saved: dict[str, int] = {}
    bad = []
    for entry, code, msg in sorted(results, key=lambda r: (r[0]["ats"], r[0]["company"])):
        flag = "ok " if code == 200 else ("empty" if code == 204 else "BAD")
        print(f"  {code:>4} {flag:5} {entry['ats']:15} {entry['company'][:34]:34} {msg}")
        report["ats"].append({"company": entry["company"], "ats": entry["ats"], "slug": entry["slug"], "status": code, "msg": msg})
        if code not in (200, 204):
            bad.append(entry)
        if code == 200 and not args.no_fixtures and saved.get(entry["ats"], 0) < FIXTURES_PER_ATS:
            mod = ATS[entry["ats"]]
            if entry["ats"] == "smartrecruiters" and "postings" in msg and int(msg.split()[0]) > 600:
                continue
            try:
                raw = mod.fetch_raw(entry["slug"], http)
                save(f"{entry['ats']}__{safe(entry['slug'])}.json", trim_ats(entry["ats"], raw, fs))
                saved[entry["ats"]] = saved.get(entry["ats"], 0) + 1
            except Exception as exc:
                print(f"       fixture failed: {exc}")

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "smoke_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in report["ats"] if r["status"] in (200, 204))
    print(f"\n{ok}/{len(report['ats'])} ATS slugs reachable; {len(bad)} bad")
    for e in bad:
        print(f"  BAD {e['ats']}:{e['slug']} ({e['company']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
