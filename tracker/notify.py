from __future__ import annotations

import os

from .geo import COUNTRY_NAMES

MAX_LINES = 50
SITE_URL = "https://luca7ok.github.io/job-scrapper/"


def _countries(codes: list[str]) -> str:
    return ", ".join(COUNTRY_NAMES.get(c, c) for c in codes)


def _line(r: dict) -> str:
    bits = [r.get("locations") or _countries(r.get("countries") or [])]
    if r.get("start_label") and r["start_label"] != "Not stated":
        bits.append(r["start_label"])
    meta = " · ".join(b for b in bits if b)
    line = f"- **{r['company']}**: [{r['title']}]({r['url']})"
    return f"{line} — {meta}" if meta else line


def build_notification(new_roles: list[dict], hits: list[dict], roles_by_id: dict[str, dict], today: str) -> str | None:
    hit_ids = [rid for h in hits for rid in h["role_ids"]]
    ordered: list[dict] = [roles_by_id[rid] for rid in hit_ids if rid in roles_by_id]
    seen = {r["id"] for r in ordered}
    rest = [r for r in new_roles if r["id"] not in seen]
    rest.sort(key=lambda r: (r.get("start_bucket") != "july", r.get("countries") == ["GB"], not r.get("midsize"), r["company"].lower()))
    ordered.extend(rest)
    if not ordered:
        return None

    total = len(ordered)
    lines = [f"{total} new role{'s' if total != 1 else ''} on {today}.", ""]
    lines.extend(_line(r) for r in ordered[:MAX_LINES])
    lines.append("")
    if total > MAX_LINES:
        lines.append(f"And {total - MAX_LINES} more on the site.")
        lines.append("")
    lines.append(f"[Open the tracker]({SITE_URL})")
    return "\n".join(lines) + "\n"


def summary_line(new_count: int, hits: list[dict], july_count: int) -> str:
    parts = []
    if hits:
        names = ", ".join(h["company"] for h in hits[:3])
        parts.append(f"🔔 {names} opened")
    parts.append(f"{new_count} new role{'s' if new_count != 1 else ''}")
    if july_count:
        parts.append(f"{july_count} July start")
    return " · ".join(parts)


def push_ntfy(http, message: str, title: str = "EU SWE 2027") -> bool:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    resp = http.post(
        f"https://ntfy.sh/{topic}",
        content=message.encode("utf-8"),
        headers={"Title": title, "Click": SITE_URL, "Tags": "briefcase"},
    )
    return resp.status_code < 300
