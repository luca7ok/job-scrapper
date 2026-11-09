from __future__ import annotations

from ..schema import Posting
from ..text import html_to_text, iso_from_string

NAME = "greenhouse"
HOSTS = ["https://boards-api.greenhouse.io", "https://boards-api.eu.greenhouse.io"]


def fetch_raw(slug: str, http) -> dict:
    last = None
    for host in HOSTS:
        resp = http.get(f"{host}/v1/boards/{slug}/jobs")
        if resp.status_code == 200:
            data = resp.json()
            data["_host"] = host
            return data
        last = resp
    last.raise_for_status()
    return {}


def _locations(job: dict) -> list[str]:
    locs = []
    name = (job.get("location") or {}).get("name")
    if name:
        locs.append(name)
    for meta in job.get("metadata") or []:
        if "location" in str(meta.get("name", "")).lower():
            val = meta.get("value")
            if isinstance(val, list):
                locs.extend(str(v) for v in val if v)
            elif val:
                locs.append(str(val))
    for office in job.get("offices") or []:
        for key in ("location", "name"):
            if office.get(key):
                locs.append(office[key])
                break
    return locs


def _detail(http, host: str, slug: str, job_id) -> dict:
    resp = http.get(f"{host}/v1/boards/{slug}/jobs/{job_id}")
    resp.raise_for_status()
    d = resp.json()
    return {"description": html_to_text(d.get("content"), 4000), "locations": _locations(d)}


def parse(raw: dict, entry: dict, http=None) -> list[Posting]:
    host = raw.get("_host", HOSTS[0])
    slug = entry["slug"]
    out = []
    for job in raw.get("jobs") or []:
        jid = job.get("id")
        detail = (lambda jid=jid: _detail(http, host, slug, jid)) if http is not None else None
        desc = html_to_text(job.get("content"), 4000) if job.get("content") else ""
        out.append(Posting(
            company=entry["company"],
            title=(job.get("title") or "").strip(),
            locations=_locations(job),
            url=job.get("absolute_url") or "",
            source=NAME,
            posted=iso_from_string(job.get("first_published") or job.get("updated_at")),
            description=desc,
            geo_pending=True,
            detail=detail,
        ))
    return out
