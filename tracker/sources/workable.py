from __future__ import annotations

import re

from ..schema import Posting
from ..text import html_to_text, iso_from_string

NAME = "workable"


def fetch_raw(slug: str, http) -> dict:
    resp = http.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
    resp.raise_for_status()
    return resp.json()


def parse(raw: dict, entry: dict, http=None) -> list[Posting]:
    out = []
    for j in raw.get("jobs") or []:
        locs, countries = [], []
        for loc in j.get("locations") or []:
            if loc.get("hidden"):
                continue
            parts = [loc.get("city"), loc.get("region"), loc.get("country")]
            locs.append(", ".join(p for p in parts if p))
            cc = (loc.get("countryCode") or "").upper()
            if cc and cc not in countries:
                countries.append(cc)
        if not locs:
            parts = [j.get("city"), j.get("state"), j.get("country")]
            if any(parts):
                locs.append(", ".join(p for p in parts if p))
        if j.get("telecommuting") and not locs:
            locs.append("Remote")
        emp = f"{j.get('employment_type') or ''} {j.get('experience') or ''}"
        hint = "Internship" if re.search(r"(?i)intern", emp) else ("New grad" if re.search(r"(?i)entry level", emp) else None)
        out.append(Posting(
            company=entry["company"],
            title=(j.get("title") or "").strip(),
            locations=locs,
            url=j.get("url") or j.get("shortlink") or "",
            source=NAME,
            posted=iso_from_string(j.get("published_on") or j.get("created_at")),
            description=html_to_text(j.get("description"), 4000),
            kind_hint=hint,
            countries=countries or None,
        ))
    return out
