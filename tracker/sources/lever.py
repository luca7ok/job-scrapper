from __future__ import annotations

import re

from ..schema import Posting
from ..text import iso_from_unix

NAME = "lever"
HOSTS = ["https://api.lever.co", "https://api.eu.lever.co"]


def fetch_raw(slug: str, http) -> dict:
    last = None
    for host in HOSTS:
        resp = http.get(f"{host}/v0/postings/{slug}?mode=json")
        if resp.status_code == 200:
            return {"_host": host, "postings": resp.json()}
        last = resp
    last.raise_for_status()
    return {}


def parse(raw: dict, entry: dict, http=None) -> list[Posting]:
    out = []
    for p in raw.get("postings") or []:
        cats = p.get("categories") or {}
        locs = list(cats.get("allLocations") or [])
        if cats.get("location") and cats["location"] not in locs:
            locs.insert(0, cats["location"])
        country = (p.get("country") or "").upper()
        commitment = str(cats.get("commitment") or "")
        hint = "Internship" if re.search(r"(?i)intern|stage|praktik", commitment) else None
        desc = p.get("descriptionPlain") or ""
        for lst in p.get("lists") or []:
            desc += "\n" + str(lst.get("text", ""))
        desc += "\n" + (p.get("additionalPlain") or "")
        out.append(Posting(
            company=entry["company"],
            title=(p.get("text") or "").strip(),
            locations=locs,
            url=p.get("hostedUrl") or "",
            source=NAME,
            posted=iso_from_unix(p.get("createdAt")),
            description=desc[:4000],
            kind_hint=hint,
            countries=[country] if len(country) == 2 else None,
        ))
    return out
