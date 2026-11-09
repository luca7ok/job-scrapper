from __future__ import annotations

import re

from ..schema import Posting
from ..text import iso_from_unix

NAME = "simplify"
FEEDS = {
    "simplify_intern": ("https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json", "Internship"),
    "simplify_newgrad": ("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json", "New grad"),
}
MIN_POSTED = "2026-07-01"
_OLD_TERM = re.compile(r"\b(2024|2025|2026)\b")


def fetch_raw(feed: str, http) -> list:
    url, _ = FEEDS[feed]
    resp = http.get(url)
    resp.raise_for_status()
    return resp.json()


def _keep(item: dict) -> bool:
    if not (item.get("active") and item.get("is_visible", True)):
        return False
    terms = [t for t in item.get("terms") or [] if t and t != "N/A"]
    if terms and all(_OLD_TERM.search(t) for t in terms):
        return False
    posted = iso_from_unix(item.get("date_posted"))
    if posted and posted < MIN_POSTED:
        return False
    return True


def parse(raw: list, feed: str) -> list[Posting]:
    _, kind = FEEDS[feed]
    out = []
    for item in raw:
        if not _keep(item):
            continue
        degrees = item.get("degrees") or []
        k = kind
        if degrees and all(str(d).lower() == "phd" for d in degrees):
            k = "PhD / research"
        out.append(Posting(
            company=item.get("company_name", "").strip(),
            title=item.get("title", "").strip(),
            locations=list(item.get("locations") or []),
            url=item.get("url", ""),
            source=NAME,
            posted=iso_from_unix(item.get("date_posted")),
            kind_hint=k,
            terms=[t for t in item.get("terms") or [] if t and t != "N/A"],
        ))
    return out
