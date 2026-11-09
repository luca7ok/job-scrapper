from __future__ import annotations

import re
from datetime import date

from ..schema import Posting
from ..text import iso_days_ago
from .markdown import link_of, plain, tables

NAME = "speedyapply"
FEEDS = {
    "speedyapply_intern": ("https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/INTERN_INTL.md", "Internship"),
    "speedyapply_newgrad": ("https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_INTL.md", "New grad"),
}


def fetch_raw(feed: str, http) -> str:
    url, _ = FEEDS[feed]
    resp = http.get(url)
    resp.raise_for_status()
    return resp.text


def _col(header: list[str], *names: str) -> int | None:
    for n in names:
        for i, h in enumerate(header):
            if h.startswith(n):
                return i
    return None


def parse(raw: str, feed: str, today: date | None = None) -> list[Posting]:
    _, kind = FEEDS[feed]
    today = today or date.today()
    out = []
    for _, header, rows in tables(raw):
        ci = _col(header, "company")
        ti = _col(header, "position", "role", "title")
        li = _col(header, "location")
        pi = _col(header, "posting", "apply", "link")
        ai = _col(header, "age")
        if None in (ci, ti, li, pi):
            continue
        for row in rows:
            if len(row) <= max(ci, ti, li, pi):
                continue
            url = link_of(row[pi])
            if not url:
                continue
            posted = None
            if ai is not None and ai < len(row):
                m = re.match(r"(\d+)\s*d", plain(row[ai]))
                if m:
                    posted = iso_days_ago(int(m.group(1)), today)
            loc = plain(row[li])
            out.append(Posting(
                company=plain(row[ci]),
                title=plain(row[ti]),
                locations=[loc] if loc else [],
                url=url,
                source=NAME,
                posted=posted,
                kind_hint=kind,
            ))
    return out
