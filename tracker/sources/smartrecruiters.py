from __future__ import annotations

from ..schema import Posting
from ..text import html_to_text, iso_from_string

NAME = "smartrecruiters"
PAGE = 100
MAX_PAGES = 60


def fetch_raw(slug: str, http) -> dict:
    content: list = []
    total = None
    offset = 0
    for _ in range(MAX_PAGES):
        resp = http.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit={PAGE}&offset={offset}")
        resp.raise_for_status()
        d = resp.json()
        total = d.get("totalFound", 0)
        batch = d.get("content") or []
        content.extend(batch)
        offset += PAGE
        if not batch or offset >= total:
            break
    return {"totalFound": total, "content": content}


def _detail(http, slug: str, pid: str) -> dict:
    resp = http.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{pid}")
    resp.raise_for_status()
    d = resp.json()
    sections = ((d.get("jobAd") or {}).get("sections") or {})
    parts = [html_to_text((sections.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation")]
    return {"description": "\n".join(p for p in parts if p)[:4000]}


def parse(raw: dict, entry: dict, http=None) -> list[Posting]:
    slug = entry["slug"]
    out = []
    for p in raw.get("content") or []:
        loc = p.get("location") or {}
        full = loc.get("fullLocation") or ", ".join(x for x in [loc.get("city"), loc.get("country", "").upper()] if x)
        cc = (loc.get("country") or "").upper()
        level = str((p.get("experienceLevel") or {}).get("id") or "")
        hint = "Internship" if level == "internship" else ("New grad" if level == "entry_level" else None)
        pid = p.get("id")
        detail = (lambda pid=pid: _detail(http, slug, pid)) if http is not None else None
        out.append(Posting(
            company=entry["company"],
            title=(p.get("name") or "").strip(),
            locations=[full] if full else [],
            url=f"https://jobs.smartrecruiters.com/{slug}/{pid}",
            source=NAME,
            posted=iso_from_string(p.get("releasedDate")),
            kind_hint=hint,
            countries=[cc] if len(cc) == 2 else None,
            detail=detail,
        ))
    return out
