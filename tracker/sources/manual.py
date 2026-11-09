from __future__ import annotations

import re

from ..geo import countries_from_names
from ..schema import Posting

NAME = "manual"


def parse(entries: list[dict]) -> list[Posting]:
    out = []
    for e in entries:
        if not e.get("company") or not e.get("title"):
            continue
        locs = [s.strip() for s in re.split(r";", str(e.get("locations") or "")) if s.strip()]
        out.append(Posting(
            company=str(e["company"]).strip(),
            title=str(e["title"]).strip(),
            locations=locs,
            url=str(e.get("url") or ""),
            source=NAME,
            posted=None,
            kind_hint=e.get("kind") or "Internship",
            countries=countries_from_names(str(e.get("countries") or "")),
            start_hint=str(e.get("start") or "Not stated"),
            note=str(e.get("note") or ""),
            status=str(e.get("status") or "open"),
            midsize=bool(e.get("midsize")),
            trusted=True,
        ))
    return out
