from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as cfgmod
from . import dates
from .filters import FilterSet
from .geo import EUROPE_CODES, clean_locations, europe_countries
from .http import client
from .merge import FeedStatus, merge_state
from .notify import build_notification, push_ntfy, summary_line
from .schema import Posting, Role, norm_company, role_id
from .sources import AGGREGATORS, ATS, LISTS, manual
from .sources import adzuna as adzuna_mod

ROOT = Path(__file__).resolve().parent.parent
ATS_SOURCES = set(ATS)
LIST_SOURCES = {"simplify", "speedyapply", "earlycareers"}
RECENT_CLOSED_DAYS = 14
MANY_COUNTRIES = 10
LEVEL_UNCLEAR = "Level not stated in the title."


@dataclass
class FeedRun:
    key: str
    source: str
    ok: bool = False
    skipped: bool = False
    raw_count: int = 0
    kept: list[Role] = field(default_factory=list)
    error: str | None = None
    detail_errors: int = 0
    seconds: float = 0.0


def safe(slug: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", slug)


class Processor:
    def __init__(self, cfg: cfgmod.Config, fs: FilterSet, today: date, fetch_details: bool):
        self.cfg = cfg
        self.fs = fs
        self.today = today
        self.fetch_details = fetch_details
        self.include_tr = bool(cfg.setting("include_turkey", False))
        self.allowed = set(EUROPE_CODES) | {"EU"}
        if not self.include_tr:
            self.allowed.discard("TR")

    def _kind(self, p: Posting) -> tuple[str | None, str]:
        title_kind = self.fs.kind(p.title)
        if p.trusted:
            return p.kind_hint or title_kind or "Internship", ""
        if p.source in LIST_SOURCES:
            if title_kind == "PhD / research":
                return title_kind, ""
            return p.kind_hint or title_kind, ""
        if p.source in ATS_SOURCES:
            k = title_kind or p.kind_hint
            if k:
                return k, ""
            if self.cfg.is_watched(p.company):
                return "New grad", LEVEL_UNCLEAR
            return None, ""
        return title_kind, ""

    def _countries(self, p: Posting) -> list[str]:
        out: list[str] = []
        for c in p.countries or []:
            c = "GB" if c == "UK" else c
            if c in self.allowed and c not in out:
                out.append(c)
        for loc in p.locations:
            for c in europe_countries(loc, include_tr=self.include_tr):
                if c not in out:
                    out.append(c)
        return out

    def _load_detail(self, p: Posting, run: FeedRun) -> None:
        if not (self.fetch_details and p.detail):
            return
        try:
            d = p.detail() or {}
        except Exception:
            run.detail_errors += 1
            d = {}
        p.detail = None
        if d.get("description"):
            p.description = d["description"]
        for loc in d.get("locations") or []:
            if loc and loc not in p.locations:
                p.locations.append(loc)

    def process(self, p: Posting, run: FeedRun) -> Role | None:
        if not p.title or not p.company:
            return None
        if not p.trusted:
            if not self.fs.is_swe(p.title) or not self.fs.is_2027_relevant(p.title):
                return None
        kind, kind_note = self._kind(p)
        if not kind:
            return None

        countries = self._countries(p)
        if not countries and p.geo_pending and p.detail:
            self._load_detail(p, run)
            countries = self._countries(p)
        if not countries and p.default_country and not any(europe_countries(l) for l in p.locations):
            if not p.locations or not _looks_non_european(p.locations):
                countries = [p.default_country]
        real = [c for c in countries if c != "EU"]
        if len(real) >= MANY_COUNTRIES:
            countries = ["EU"]
        if not countries:
            if p.trusted:
                countries = []
            else:
                return None

        if p.detail and not p.description:
            self._load_detail(p, run)

        if p.trusted:
            label, month, bucket = dates.from_label(p.start_hint or "Not stated")
        else:
            label, month, bucket = dates.extract_start(p.title, p.description)
            for term in p.terms:
                t = dates.from_term(term)
                if t and dates.richness(*t) > dates.richness(label, month, bucket):
                    label, month, bucket = t

        midsize = bool(p.midsize) if p.midsize is not None else self.cfg.is_midsize(p.company)
        if not midsize:
            midsize = self.cfg.is_midsize(p.company)
        locations = clean_locations(p.locations)
        note = " ".join(x for x in (p.note, kind_note) if x)
        return Role(
            id=role_id(p.url, p.company, p.title, locations),
            company=p.company,
            title=p.title,
            kind=kind,
            countries=countries,
            locations=locations,
            start_label=label,
            start_month=month,
            start_bucket=bucket,
            url=p.url,
            source=p.source,
            midsize=midsize,
            posted=p.posted,
            first_seen="",
            last_seen="",
            status="expected" if p.status == "expected" else "open",
            is_new=False,
            note=note,
            sources=[p.source],
            feeds=[run.key],
            level_unclear=kind_note == LEVEL_UNCLEAR,
        )


_NON_EU_HINT = re.compile(r"(?i)\b(usa|united states|canada|india|china|remote\s*-\s*us|us remote|new york|london, on)\b")


def _looks_non_european(locs: list[str]) -> bool:
    return any(_NON_EU_HINT.search(l) for l in locs)


def _fixture(fixtures: Path, name: str):
    path = fixtures / name
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


def run_feed(key: str, source: str, fetch, parse, proc: Processor) -> FeedRun:
    run = FeedRun(key=key, source=source)
    t0 = time.monotonic()
    try:
        raw = fetch()
        if raw is None:
            run.skipped = True
            return run
        postings = parse(raw)
        run.raw_count = len(postings)
        for p in postings:
            p.feed = key
            role = proc.process(p, run)
            if role is not None:
                run.kept.append(role)
        run.ok = True
    except adzuna_mod.MissingKey as exc:
        run.skipped = True
        run.error = str(exc)
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
    finally:
        run.seconds = time.monotonic() - t0
    return run


def plan_feeds(cfg: cfgmod.Config, proc: Processor, offline: bool, fixtures: Path, only: set[str] | None, today: date):
    http = None if offline else client()
    jobs = []

    def want(source: str) -> bool:
        return not only or source in only

    for feed, mod in LISTS.items():
        src = mod.NAME
        if offline:
            ext = ".json" if src == "simplify" else ".md"
            fetch = (lambda feed=feed, ext=ext: _fixture(fixtures, feed + ext))
        else:
            fetch = (lambda feed=feed, mod=mod: mod.fetch_raw(feed, http))
        if src == "speedyapply":
            parse = (lambda raw, feed=feed, mod=mod: mod.parse(raw, feed, today=today))
        else:
            parse = (lambda raw, feed=feed, mod=mod: mod.parse(raw, feed))
        jobs.append((feed, src, fetch, parse, want(src)))

    jobs.append(("manual", "manual", lambda: cfg.manual_entries, manual.parse, want("manual")))

    agg_cfg = cfg.setting("aggregators", {}) or {}
    for feed, mod in AGGREGATORS.items():
        enabled = bool(agg_cfg.get(feed, False))
        if offline:
            fetch = (lambda feed=feed: _fixture(fixtures, f"{feed}.json"))
        elif feed == "arbeitnow":
            pages = int(cfg.setting("arbeitnow_pages", 10))
            fetch = (lambda mod=mod, feed=feed, pages=pages: mod.fetch_raw(feed, http, max_pages=pages))
        else:
            fetch = (lambda mod=mod, feed=feed: mod.fetch_raw(feed, http))
        parse = (lambda raw, mod=mod, feed=feed: mod.parse(raw, feed))
        jobs.append((feed, mod.NAME, fetch, parse, enabled and want(mod.NAME)))

    for entry in cfg.ats_companies:
        ats = entry.get("ats")
        mod = ATS.get(ats)
        if mod is None:
            continue
        key = f"{ats}:{entry['slug']}"
        enabled = not entry.get("disabled") and want(ats)
        if offline:
            fetch = (lambda ats=ats, entry=entry: _fixture(fixtures, f"{ats}__{safe(entry['slug'])}.json"))
        else:
            fetch = (lambda mod=mod, entry=entry: mod.fetch_raw(entry["slug"], http))
        if ats == "workday":
            parse = (lambda raw, mod=mod, entry=entry: mod.parse(raw, entry, http=http, today=today))
        else:
            parse = (lambda raw, mod=mod, entry=entry: mod.parse(raw, entry, http=http))
        jobs.append((key, ats, fetch, parse, enabled))
    return jobs


def build_watchlist(cfg: cfgmod.Config, roles: dict[str, dict]) -> list[dict]:
    open_by_company: dict[str, list[dict]] = {}
    for r in roles.values():
        if r.get("status") == "open":
            open_by_company.setdefault(norm_company(r["company"]), []).append(r)
    out = []
    seen = set()
    for w in cfg.watchlist:
        c = norm_company(w["company"])
        seen.add(c)
        live = [r for r in open_by_company.get(c, []) if not r.get("level_unclear")]
        out.append({
            "company": w["company"],
            "type": "career_site",
            "url": w.get("url", ""),
            "note": w.get("note", ""),
            "midsize": bool(w.get("midsize")),
            "last_checked": str(w.get("last_checked") or ""),
            "open_now": bool(live),
            "open_roles": len(live),
            "role_ids": [r["id"] for r in live][:20],
        })
    for m in cfg.manual_entries:
        if m.get("status") != "expected":
            continue
        c = norm_company(m["company"])
        live = [r for r in open_by_company.get(c, []) if not r.get("level_unclear")]
        entry = {
            "company": m["company"],
            "type": "expected",
            "title": m.get("title", ""),
            "url": m.get("url", ""),
            "note": m.get("note", ""),
            "start": m.get("start", ""),
            "midsize": bool(m.get("midsize")),
            "last_checked": str(m.get("last_checked") or ""),
            "open_now": bool(live),
            "open_roles": len(live),
            "role_ids": [r["id"] for r in live][:20],
        }
        if c in seen:
            for w in out:
                if norm_company(w["company"]) == c and w["type"] == "career_site":
                    w.setdefault("programmes", []).append({"title": entry["title"], "start": entry["start"], "url": entry["url"], "note": entry["note"]})
                    break
            continue
        out.append(entry)
    out.sort(key=lambda w: (not w["open_now"], w["company"].lower()))
    return out


def compute_stats(public_roles: list[dict]) -> dict:
    open_roles = [r for r in public_roles if r["status"] == "open"]
    companies = {norm_company(r["company"]) for r in open_roles}
    outside = [r for r in open_roles if any(c != "GB" for c in r["countries"])]
    midsize = [r for r in outside if r.get("midsize")]
    return {
        "companies": len(companies),
        "roles": len(open_roles),
        "outside_uk": len(outside),
        "midsize_eu": len(midsize),
        "new_week": sum(1 for r in open_roles if r.get("is_new")),
        "july": sum(1 for r in open_roles if r.get("start_bucket") == "july"),
        "expected": sum(1 for r in public_roles if r["status"] == "expected"),
        "recently_closed": sum(1 for r in public_roles if r["status"] == "closed"),
    }


def write_report(path: Path, runs: list[FeedRun], result, stats: dict, today: str, seconds: float, push_status: str | None = None) -> None:
    lines = [f"# Run report {today}", ""]
    lines.append(f"Finished in {seconds:.0f}s. Open roles: **{stats['roles']}** ({stats['outside_uk']} outside the UK, {stats['midsize_eu']} at mid-size companies, {stats['july']} July start).")
    lines.append("")
    lines.append(f"New: {len(result.new_ids)} · Closed: {len(result.closed_ids)} · Reopened: {len(result.reopened_ids)}" + (" · first run (bootstrap)" if result.bootstrap else ""))
    lines.append("")
    if push_status:
        lines.append(f"Phone notification (ntfy): {push_status}.")
        lines.append("")
    if result.hits:
        lines.append("## 🔔 Newly opened")
        for h in result.hits:
            lines.append(f"- {h['company']} ({len(h['role_ids'])} role{'s' if len(h['role_ids']) != 1 else ''})")
        lines.append("")
    if result.outages:
        lines.append("## Possible outages (roles kept open)")
        for k in result.outages:
            lines.append(f"- {k}")
        lines.append("")
    errors = [r for r in runs if r.error and not r.skipped]
    if errors:
        lines.append("## Errors")
        for r in errors:
            lines.append(f"- `{r.key}`: {r.error}")
        lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append("| feed | status | postings | kept | detail errors | seconds |")
    lines.append("|---|---|---:|---:|---:|---:|")
    by_source: dict[str, list[FeedRun]] = {}
    for r in runs:
        by_source.setdefault(r.source, []).append(r)
    for r in runs:
        if r.source in ATS_SOURCES:
            continue
        status = "ok" if r.ok else ("skipped" if r.skipped else "error")
        lines.append(f"| {r.key} | {status} | {r.raw_count} | {len(r.kept)} | {r.detail_errors} | {r.seconds:.1f} |")
    for src in sorted(ATS_SOURCES):
        rs = [r for r in by_source.get(src, []) if not r.skipped]
        if not rs:
            continue
        ok = sum(1 for r in rs if r.ok)
        lines.append(f"| {src} ({ok}/{len(rs)} companies ok) | {'ok' if ok == len(rs) else 'partial'} | {sum(r.raw_count for r in rs)} | {sum(len(r.kept) for r in rs)} | {sum(r.detail_errors for r in rs)} | {sum(r.seconds for r in rs):.1f} |")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tracker.update")
    ap.add_argument("--offline", action="store_true", help="read every source from tests/fixtures")
    ap.add_argument("--only", action="append", help="run only this source (repeatable), e.g. greenhouse, simplify, manual")
    ap.add_argument("--config", default=None)
    ap.add_argument("--fixtures", default=str(ROOT / "tests" / "fixtures"))
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--site-dir", default=str(ROOT / "site"))
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD)")
    ap.add_argument("--no-details", action="store_true", help="skip per-job detail requests")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    cfg = cfgmod.load(args.config)
    fs = FilterSet.from_config(cfg.filters)
    proc = Processor(cfg, fs, today, fetch_details=not args.offline and not args.no_details)
    data_dir, site_dir = Path(args.data_dir), Path(args.site_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "data").mkdir(parents=True, exist_ok=True)
    only = set(args.only) if args.only else None

    jobs = plan_feeds(cfg, proc, args.offline, Path(args.fixtures), only, today)
    runs: list[FeedRun] = []
    active = [j for j in jobs if j[4]]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_feed, key, src, fetch, parse, proc) for key, src, fetch, parse, _ in active]
        for f in futures:
            runs.append(f.result())
    for key, src, *_rest, enabled in jobs:
        if not enabled:
            runs.append(FeedRun(key=key, source=src, skipped=True))

    feeds = {r.key: FeedStatus(ok=r.ok, count=len(r.kept), error=r.error, skipped=r.skipped) for r in runs}
    candidates = [role for r in runs for role in r.kept]

    state_path = data_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    result = merge_state(state, candidates, feeds, today, cfg.watch_names)
    roles = result.state["roles"]

    recent = (today - timedelta(days=RECENT_CLOSED_DAYS)).isoformat()
    public = []
    for rd in roles.values():
        r = Role.from_dict(rd)
        r.midsize = r.midsize or cfg.is_midsize(r.company)
        if r.status in ("open", "expected") or (r.status == "closed" and (r.closed_on or "") >= recent):
            public.append(r.public())
    public.sort(key=lambda r: (r["company"].lower(), r["title"].lower()))
    stats = compute_stats(public)
    watchlist = build_watchlist(cfg, roles)

    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    site_payload = {"generated_at": generated, "today": today.isoformat(), "stats": stats, "watchlist": watchlist, "roles": public}
    (site_dir / "data" / "roles.json").write_text(json.dumps(site_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    state_path.write_text(json.dumps(result.state, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    hist = data_dir / "history"
    hist.mkdir(exist_ok=True)
    (hist / f"{today.isoformat()}.json").write_text(json.dumps({
        "date": today.isoformat(), "stats": stats, "new": result.new_ids, "closed": result.closed_ids,
        "reopened": result.reopened_ids, "hits": result.hits, "outages": result.outages,
        "errors": {r.key: r.error for r in runs if r.error and not r.skipped},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    notify_path = data_dir / "notify.md"
    new_public = [Role.from_dict(roles[i]).public() for i in result.new_ids if roles[i].get("status") == "open"]
    body = build_notification(new_public, result.hits, {k: Role.from_dict(v).public() for k, v in roles.items()}, today.isoformat())
    push_status = None
    if body and not result.bootstrap:
        notify_path.write_text(body, encoding="utf-8")
        if not args.offline:
            july = sum(1 for r in new_public if r.get("start_bucket") == "july")
            try:
                if push_ntfy(client(), summary_line(len(new_public), result.hits, july)):
                    push_status = "sent"
            except Exception as exc:
                push_status = f"failed: {type(exc).__name__}: {exc}"
    elif notify_path.exists():
        notify_path.unlink()

    seconds = time.monotonic() - t0
    write_report(data_dir / "run_report.md", runs, result, stats, today.isoformat(), seconds, push_status)
    errs = sum(1 for r in runs if r.error and not r.skipped)
    print(f"{today}: {stats['roles']} open ({stats['outside_uk']} outside UK, {stats['july']} July), "
          f"{len(result.new_ids)} new, {len(result.closed_ids)} closed, {len(result.hits)} watchlist hits, "
          f"{errs} feed errors, {seconds:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
