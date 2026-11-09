from __future__ import annotations

from ..geo import europe_countries
from ..schema import Posting
from ..text import iso_from_string

NAME = "ashby"


def fetch_raw(slug: str, http) -> dict:
    resp = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    resp.raise_for_status()
    return resp.json()


def _addr_country(addr) -> str | None:
    if not isinstance(addr, dict):
        return None
    pa = addr.get("postalAddress") or {}
    return pa.get("addressCountry")


def parse(raw: dict, entry: dict, http=None) -> list[Posting]:
    out = []
    for j in raw.get("jobs") or []:
        if j.get("isListed") is False:
            continue
        locs = []
        if j.get("location"):
            locs.append(j["location"])
        countries: list[str] = []
        main_c = _addr_country(j.get("address"))
        if main_c:
            countries.extend(europe_countries(main_c, include_tr=True))
        for sec in j.get("secondaryLocations") or []:
            if isinstance(sec, dict):
                if sec.get("location"):
                    locs.append(sec["location"])
                c = _addr_country(sec.get("address"))
                if c:
                    countries.extend(x for x in europe_countries(c, include_tr=True) if x not in countries)
        emp = str(j.get("employmentType") or "")
        hint = "Internship" if emp.lower() == "intern" else None
        out.append(Posting(
            company=entry["company"],
            title=(j.get("title") or "").strip(),
            locations=locs,
            url=j.get("jobUrl") or "",
            source=NAME,
            posted=iso_from_string(j.get("publishedAt")),
            description=(j.get("descriptionPlain") or "")[:4000],
            kind_hint=hint,
            countries=countries or None,
        ))
    return out
