from __future__ import annotations

import os
import time

from ..schema import Posting
from ..text import html_to_text, iso_from_string

NAME = "adzuna"
FEEDS = {"adzuna": None}
COUNTRIES = ["de", "fr", "nl", "it", "es", "pl", "at", "be", "ch", "gb"]
QUERIES = [
    {"what": "software", "what_or": "intern internship praktikum stage stagiaire tirocinio prácticas staż"},
    {"what": "software", "what_or": "graduate junior trainee absolvent"},
]
PER_PAGE = 50
MAX_PAGES = 2
MIN_INTERVAL = 2.6


class MissingKey(Exception):
    pass


def credentials() -> tuple[str, str] | None:
    app_id = os.environ.get("ADZUNA_ID", "").strip()
    app_key = os.environ.get("ADZUNA_KEY", "").strip()
    if not app_id or not app_key:
        return None
    return app_id, app_key


def fetch_raw(feed: str, http, countries: list[str] | None = None) -> dict:
    creds = credentials()
    if creds is None:
        raise MissingKey("ADZUNA_ID / ADZUNA_KEY not set")
    app_id, app_key = creds
    results: list = []
    last = 0.0
    for cc in countries or COUNTRIES:
        for q in QUERIES:
            for page in range(1, MAX_PAGES + 1):
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": PER_PAGE,
                    "max_days_old": 90,
                    "content-type": "application/json",
                    **q,
                }
                wait = MIN_INTERVAL - (time.monotonic() - last)
                if wait > 0:
                    time.sleep(wait)
                last = time.monotonic()
                resp = http.get(f"https://api.adzuna.com/v1/api/jobs/{cc}/search/{page}", params=params)
                resp.raise_for_status()
                batch = resp.json().get("results") or []
                for r in batch:
                    r["_cc"] = cc
                results.extend(batch)
                if len(batch) < PER_PAGE:
                    break
    return {"results": results}


def parse(raw: dict, feed: str = "adzuna") -> list[Posting]:
    out = []
    for r in raw.get("results") or []:
        loc = (r.get("location") or {}).get("display_name") or ""
        cc = (r.get("_cc") or "").upper()
        cc = "GB" if cc == "UK" else cc
        out.append(Posting(
            company=((r.get("company") or {}).get("display_name") or "").strip(),
            title=" ".join(html_to_text(r.get("title") or "").split()),
            locations=[loc] if loc else [],
            url=r.get("redirect_url") or "",
            source=NAME,
            posted=iso_from_string(r.get("created")),
            description=html_to_text(r.get("description"), 4000),
            countries=[cc] if cc else None,
        ))
    return out
