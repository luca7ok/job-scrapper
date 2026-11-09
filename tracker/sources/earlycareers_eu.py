from __future__ import annotations

from ..schema import Posting
from ..text import nice_case, sentence_case
from .markdown import link_of, plain, tables

NAME = "earlycareers"
URLS = [
    "https://raw.githubusercontent.com/LorenzoLaCorte/european-tech-internships-2027/main/README.md",
    "https://raw.githubusercontent.com/LorenzoLaCorte/european-tech-internships-2026/main/README.md",
]
FEEDS = {"earlycareers": None}


def fetch_raw(feed: str, http) -> str:
    last = None
    for url in URLS:
        resp = http.get(url)
        if resp.status_code == 200:
            return resp.text
        last = resp
    last.raise_for_status()
    return ""


def _kind(section: str) -> str | None:
    s = section.lower()
    if "phd" in s:
        return "PhD / research"
    if "new grad" in s or "graduate" in s:
        return "New grad"
    if "intern" in s:
        return "Internship"
    return None


def parse(raw: str, feed: str = "earlycareers") -> list[Posting]:
    out = []
    for section, header, rows in tables(raw):
        kind = _kind(section)
        if kind is None or "company" not in header or "title" not in header:
            continue
        ci, ti = header.index("company"), header.index("title")
        li = header.index("location") if "location" in header else None
        ki = header.index("link") if "link" in header else len(header) - 1
        for row in rows:
            if len(row) <= max(ci, ti, ki):
                continue
            url = link_of(row[ki])
            if not url:
                continue
            loc = plain(row[li]) if li is not None else ""
            out.append(Posting(
                company=nice_case(plain(row[ci])),
                title=sentence_case(plain(row[ti])),
                locations=[nice_case(loc)] if loc else [],
                url=url,
                source=NAME,
                kind_hint=kind,
            ))
    return out
