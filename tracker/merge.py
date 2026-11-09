from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from .dates import richness
from .geo import clean_locations
from .schema import SOURCE_PRIORITY, Role, norm_company, norm_title

CLOSE_AFTER_MISSING_RUNS = 2
FUZZY_WINDOW_DAYS = 30
NEW_DAYS = 7


@dataclass
class FeedStatus:
    ok: bool
    count: int
    error: str | None = None
    skipped: bool = False


@dataclass
class MergeResult:
    state: dict
    new_ids: list[str] = field(default_factory=list)
    closed_ids: list[str] = field(default_factory=list)
    reopened_ids: list[str] = field(default_factory=list)
    hits: list[dict] = field(default_factory=list)
    outages: list[str] = field(default_factory=list)
    bootstrap: bool = False


def _prio(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 9)


def _days_apart(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except ValueError:
        return None


def fuzzy_keys(role: Role) -> list[tuple[str, str, str]]:
    c, t = norm_company(role.company), norm_title(role.title)
    return [(c, t, cc) for cc in (role.countries or ["?"])]


def combine(a: Role, b: Role) -> Role:
    best, other = (a, b) if _prio(a.source) <= _prio(b.source) else (b, a)
    merged = replace(best)
    merged.countries = list(dict.fromkeys(best.countries + other.countries))
    if best.source != "manual":
        merged.locations = clean_locations((best.locations + ";" + other.locations).split(";"))
    merged.sources = list(dict.fromkeys(best.sources + other.sources))
    merged.feeds = list(dict.fromkeys(best.feeds + other.feeds))
    if richness(other.start_label, other.start_month, other.start_bucket) > richness(best.start_label, best.start_month, best.start_bucket):
        merged.start_label, merged.start_month, merged.start_bucket = other.start_label, other.start_month, other.start_bucket
    posts = [p for p in (best.posted, other.posted) if p]
    merged.posted = min(posts) if posts else None
    merged.midsize = best.midsize or other.midsize
    if not merged.note and other.note:
        merged.note = other.note
    if best.status == "expected" and other.status == "open":
        merged.status = "open"
    return merged


def dedupe(candidates: list[Role]) -> tuple[list[Role], dict[str, str]]:
    by_id: dict[str, Role] = {}
    aliases: dict[str, str] = {}
    for r in candidates:
        if r.id in by_id:
            by_id[r.id] = combine(by_id[r.id], r)
        else:
            by_id[r.id] = r
    index: dict[tuple, str] = {}
    out: dict[str, Role] = {}
    for rid, r in by_id.items():
        target = None
        for key in fuzzy_keys(r):
            if key in index:
                cand = out[index[key]]
                gap = _days_apart(cand.posted, r.posted)
                if gap is None or gap <= FUZZY_WINDOW_DAYS:
                    target = cand.id
                    break
        if target is None:
            out[rid] = r
            for key in fuzzy_keys(r):
                index.setdefault(key, rid)
        else:
            merged = combine(out[target], r)
            keep_id = target if _prio(out[target].source) <= _prio(r.source) else rid
            drop_id = rid if keep_id == target else target
            merged.id = keep_id
            del out[target]
            out[keep_id] = merged
            aliases[drop_id] = keep_id
            for key in fuzzy_keys(merged):
                index[key] = keep_id
    return list(out.values()), aliases


def merge_state(state: dict, candidates: list[Role], feeds: dict[str, FeedStatus], today: date, watch_names: set[str]) -> MergeResult:
    today_s = today.isoformat()
    state = dict(state or {})
    roles: dict[str, dict] = dict(state.get("roles") or {})
    aliases: dict[str, str] = dict(state.get("aliases") or {})
    feed_state: dict[str, dict] = dict(state.get("feeds") or {})
    bootstrap = not roles
    if bootstrap:
        state["bootstrapped_on"] = today_s
    boot_day = state.get("bootstrapped_on")

    result = MergeResult(state=state, bootstrap=bootstrap)

    outage = set()
    for key, st in feeds.items():
        prev = (feed_state.get(key) or {}).get("last_count", 0)
        if st.ok and st.count == 0 and prev > 0:
            outage.add(key)
    result.outages = sorted(outage)
    healthy = {k for k, st in feeds.items() if st.ok and k not in outage}
    unhealthy = {k for k, st in feeds.items() if (not st.ok and not st.skipped) or k in outage}
    skipped = {k for k, st in feeds.items() if st.skipped}

    open_before = {}
    for r in roles.values():
        if r.get("status") == "open" and not r.get("level_unclear"):
            c = norm_company(r.get("company", ""))
            open_before[c] = open_before.get(c, 0) + 1

    cands, new_aliases = dedupe(candidates)
    aliases.update(new_aliases)

    cutoff = (today - timedelta(days=FUZZY_WINDOW_DAYS)).isoformat()
    fuzzy_index: dict[tuple, str] = {}
    for rid, rd in roles.items():
        if rd.get("last_seen", "") >= cutoff:
            for key in fuzzy_keys(Role.from_dict(rd)):
                fuzzy_index.setdefault(key, rid)

    seen: set[str] = set()
    for cand in cands:
        rid = cand.id
        if rid not in roles and rid in aliases and aliases[rid] in roles:
            rid = aliases[rid]
        if rid not in roles:
            for key in fuzzy_keys(cand):
                if key in fuzzy_index and fuzzy_index[key] not in seen:
                    rid = fuzzy_index[key]
                    aliases[cand.id] = rid
                    break
        if rid in seen:
            existing = Role.from_dict(roles[rid])
            merged = combine(existing, replace(cand, id=rid))
            merged.id = rid
            merged.first_seen = existing.first_seen
            merged.last_seen = today_s
            roles[rid] = merged.to_dict()
            continue
        if rid in roles:
            old = Role.from_dict(roles[rid])
            new = replace(cand, id=rid, first_seen=old.first_seen, last_seen=today_s, missing_runs=0, closed_on=None)
            if richness(old.start_label, old.start_month, old.start_bucket) > richness(new.start_label, new.start_month, new.start_bucket) and old.source == new.source:
                new.start_label, new.start_month, new.start_bucket = old.start_label, old.start_month, old.start_bucket
            posts = [p for p in (old.posted, new.posted) if p]
            new.posted = min(posts) if posts else None
            if old.status == "closed" and new.status in ("open", "expected"):
                result.reopened_ids.append(rid)
            roles[rid] = new.to_dict()
        else:
            new = replace(cand, id=rid, first_seen=today_s, last_seen=today_s, missing_runs=0, closed_on=None)
            roles[rid] = new.to_dict()
            if not bootstrap:
                result.new_ids.append(rid)
        seen.add(rid)

    for rid, rd in roles.items():
        if rid in seen or rd.get("status") == "closed":
            continue
        rfeeds = set(rd.get("feeds") or [])
        if not rfeeds or rfeeds & (unhealthy | skipped) or not (rfeeds & healthy):
            continue
        rd["missing_runs"] = int(rd.get("missing_runs") or 0) + 1
        if rd["missing_runs"] >= CLOSE_AFTER_MISSING_RUNS:
            rd["status"] = "closed"
            rd["closed_on"] = today_s
            result.closed_ids.append(rid)

    new_cut = (today - timedelta(days=NEW_DAYS)).isoformat()
    for rd in roles.values():
        fs = rd.get("first_seen", "")
        rd["is_new"] = bool(fs >= new_cut and fs != boot_day and rd.get("status") == "open")

    hit_companies: dict[str, dict] = {}
    for rid in result.new_ids + result.reopened_ids:
        rd = roles[rid]
        if rd.get("status") != "open" or rd.get("level_unclear"):
            continue
        c = norm_company(rd.get("company", ""))
        if c in watch_names and open_before.get(c, 0) == 0:
            h = hit_companies.setdefault(c, {"company": rd["company"], "role_ids": []})
            h["role_ids"].append(rid)
    result.hits = list(hit_companies.values())

    for key, st in feeds.items():
        fs = dict(feed_state.get(key) or {})
        if st.ok and key not in outage:
            fs["last_count"] = st.count
            fs["last_ok"] = today_s
        if st.error:
            fs["last_error"] = st.error
            fs["last_error_on"] = today_s
        feed_state[key] = fs

    state["roles"] = roles
    state["aliases"] = {k: v for k, v in aliases.items() if v in roles}
    state["feeds"] = feed_state
    state["last_run"] = today_s
    state["version"] = 1
    result.state = state
    return result
