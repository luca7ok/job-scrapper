from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

SOURCE_PRIORITY = {
    "manual": 0,
    "greenhouse": 1,
    "lever": 1,
    "ashby": 1,
    "workable": 1,
    "smartrecruiters": 1,
    "workday": 1,
    "simplify": 3,
    "speedyapply": 4,
    "earlycareers": 5,
    "arbeitnow": 6,
    "adzuna": 7,
}

PUBLIC_FIELDS = (
    "id", "company", "title", "kind", "countries", "locations", "start_label", "start_month",
    "start_bucket", "url", "source", "sources", "midsize", "posted", "first_seen", "last_seen",
    "status", "is_new", "note", "closed_on", "level_unclear",
)


@dataclass
class Posting:
    company: str
    title: str
    locations: list[str]
    url: str
    source: str
    posted: str | None = None
    description: str = ""
    kind_hint: str | None = None
    countries: list[str] | None = None
    start_hint: str | None = None
    note: str = ""
    status: str = "open"
    midsize: bool | None = None
    terms: list[str] = field(default_factory=list)
    trusted: bool = False
    feed: str = ""
    geo_pending: bool = False
    default_country: str | None = None
    detail: Callable[[], dict] | None = field(default=None, repr=False, compare=False)


@dataclass
class Role:
    id: str
    company: str
    title: str
    kind: str
    countries: list[str]
    locations: str
    start_label: str
    start_month: int | None
    start_bucket: str
    url: str
    source: str
    midsize: bool
    posted: str | None
    first_seen: str
    last_seen: str
    status: str
    is_new: bool
    note: str
    sources: list[str] = field(default_factory=list)
    feeds: list[str] = field(default_factory=list)
    missing_runs: int = 0
    closed_on: str | None = None
    level_unclear: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def public(self) -> dict:
        d = asdict(self)
        return {k: d[k] for k in PUBLIC_FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "Role":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def canonical_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def role_id(url: str, company: str, title: str, location: str) -> str:
    canon = canonical_url(url)
    if canon:
        return sha1(canon)[:16]
    return sha1(f"{company}|{title}|{location}".lower())[:16]


_COMPANY_SUFFIX = re.compile(
    r"\b(gmbh|ag|se|sa|s\.a\.|s\.a|ltd|limited|inc|inc\.|llc|plc|bv|b\.v\.|nv|n\.v\.|spa|s\.p\.a\.|sas|srl|s\.r\.l\.|ab|as|oy|group|holding|holdings|co|corp|corporation|company)\b\.?",
    re.I,
)


def norm_company(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = _COMPANY_SUFFIX.sub(" ", s)
    s = re.sub(r"[^a-z0-9à-ÿ]+", "", s)
    return s


def norm_title(title: str) -> str:
    s = (title or "").lower()
    s = re.sub(r"\(m/w/d\)|\(f/m/d\)|\(m/f/d\)|\(w/m/d\)|\(m/f/x\)|\(f/m/x\)|\(all genders\)|\(h/f\)|\(f/h\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())
