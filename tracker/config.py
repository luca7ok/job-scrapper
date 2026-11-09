from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .schema import norm_company

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "companies.yaml"


@dataclass
class Config:
    raw: dict
    ats_companies: list[dict]
    watchlist: list[dict]
    manual_entries: list[dict]
    filters: dict
    settings: dict
    midsize_names: set[str] = field(default_factory=set)
    watch_names: set[str] = field(default_factory=set)

    def is_midsize(self, company: str) -> bool:
        return norm_company(company) in self.midsize_names

    def is_watched(self, company: str) -> bool:
        return norm_company(company) in self.watch_names

    def setting(self, key: str, default=None):
        return self.settings.get(key, default)


def load(path: Path | str | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    ats = [c for c in raw.get("ats_companies") or [] if c]
    watch = [c for c in raw.get("career_site_watchlist") or [] if c]
    manual = [c for c in raw.get("manual_entries") or [] if c]
    midsize = set()
    for group in (ats, watch, manual):
        for c in group:
            if c.get("midsize"):
                midsize.add(norm_company(c.get("company", "")))
    watch_names = {norm_company(c["company"]) for c in watch if c.get("company")}
    watch_names |= {norm_company(c["company"]) for c in manual if c.get("status") == "expected" and c.get("company")}
    return Config(
        raw=raw,
        ats_companies=ats,
        watchlist=watch,
        manual_entries=manual,
        filters=raw.get("filters") or {},
        settings=raw.get("settings") or {},
        midsize_names=midsize,
        watch_names=watch_names,
    )
