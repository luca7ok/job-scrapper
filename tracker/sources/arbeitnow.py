from __future__ import annotations

from ..schema import Posting
from ..text import html_to_text, iso_from_unix

NAME = "arbeitnow"
FEEDS = {"arbeitnow": None}
URL = "https://www.arbeitnow.com/api/job-board-api"
MAX_PAGES = 10


def fetch_raw(feed: str, http, max_pages: int = MAX_PAGES) -> dict:
    jobs: list = []
    for page in range(1, max_pages + 1):
        resp = http.get(f"{URL}?page={page}")
        resp.raise_for_status()
        d = resp.json()
        batch = d.get("data") or []
        jobs.extend(batch)
        if not batch or not (d.get("links") or {}).get("next"):
            break
    return {"data": jobs}


def parse(raw: dict, feed: str = "arbeitnow") -> list[Posting]:
    out = []
    for j in raw.get("data") or []:
        loc = (j.get("location") or "").strip()
        locs = [loc] if loc else []
        if j.get("remote") and not locs:
            locs = ["Remote"]
        out.append(Posting(
            company=(j.get("company_name") or "").strip(),
            title=(j.get("title") or "").strip(),
            locations=locs,
            url=j.get("url") or "",
            source=NAME,
            posted=iso_from_unix(j.get("created_at")),
            description=html_to_text(j.get("description"), 4000),
            countries=None,
            default_country=None if j.get("remote") else "DE",
        ))
    return out
