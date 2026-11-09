from __future__ import annotations

import re
from datetime import date

from ..schema import Posting
from ..text import html_to_text, iso_days_ago

NAME = "workday"
QUERIES = ["intern", "graduate", "2027", "junior", "student"]
PAGE = 20
MAX_PAGES = 5


def split_slug(slug: str) -> tuple[str, str, str]:
    tenant, wd, site = slug.split("|")
    return tenant, wd, site


def base(slug: str) -> str:
    tenant, wd, site = split_slug(slug)
    return f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"


def fetch_raw(slug: str, http) -> dict:
    url = base(slug) + "/jobs"
    seen: dict[str, dict] = {}
    for q in QUERIES:
        offset = 0
        for _ in range(MAX_PAGES):
            resp = http.post(url, json={"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": q})
            resp.raise_for_status()
            d = resp.json()
            batch = d.get("jobPostings") or []
            for p in batch:
                path = p.get("externalPath")
                if path and path not in seen:
                    seen[path] = p
            total = d.get("total") or 0
            offset += PAGE
            if not batch or offset >= total:
                break
    return {"jobPostings": list(seen.values())}


def posted_from(text: str | None, today: date) -> str | None:
    t = (text or "").lower()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return iso_days_ago(1, today)
    m = re.search(r"(\d+)\+?\s*days?", t)
    if m:
        return iso_days_ago(int(m.group(1)), today)
    return None


def _detail(http, slug: str, path: str) -> dict:
    resp = http.get(base(slug) + path)
    resp.raise_for_status()
    info = resp.json().get("jobPostingInfo") or {}
    locs = []
    if info.get("location"):
        locs.append(info["location"])
    for extra in info.get("additionalLocations") or []:
        locs.append(extra)
    country = (info.get("country") or {}).get("descriptor")
    if country:
        locs = [l if country.lower() in l.lower() else f"{l}, {country}" for l in locs] or [country]
    return {"description": html_to_text(info.get("jobDescription"), 4000), "locations": locs}


def parse(raw: dict, entry: dict, http=None, today: date | None = None) -> list[Posting]:
    today = today or date.today()
    slug = entry["slug"]
    tenant, wd, site = split_slug(slug)
    out = []
    for p in raw.get("jobPostings") or []:
        path = p.get("externalPath") or ""
        loc = p.get("locationsText") or ""
        multi = bool(re.match(r"\d+\s+locations?", loc, re.I))
        detail = (lambda path=path: _detail(http, slug, path)) if http is not None else None
        desc = html_to_text(p.get("jobDescription"), 4000) if p.get("jobDescription") else ""
        extra_locs = list(p.get("_detail_locations") or [])
        out.append(Posting(
            company=entry["company"],
            title=(p.get("title") or "").strip(),
            locations=extra_locs or ([] if multi else [loc]),
            url=f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{path}",
            source=NAME,
            posted=posted_from(p.get("postedOn"), today),
            description=desc,
            geo_pending=multi and not extra_locs,
            detail=detail,
        ))
    return out
