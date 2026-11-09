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
    if r.get("midsize"):
        bits.append("mid-size")
    meta = " · ".join(b for b in bits if b)
    return f"- **{r['company']}**: [{r['title']}]({r['url']}) — {meta}"


def build_notification(new_roles: list[dict], hits: list[dict], roles_by_id: dict[str, dict], today: str) -> str | None:
    if not new_roles and not hits:
        return None
    lines: list[str] = []
    if hits:
        lines.append("## 🔔 Newly opened")
        for h in hits:
            for rid in h["role_ids"]:
                r = roles_by_id.get(rid)
                if r:
                    lines.append(_line(r))
        lines.append("")
    hit_ids = {rid for h in hits for rid in h["role_ids"]}
    rest = [r for r in new_roles if r["id"] not in hit_ids]
    july = [r for r in rest if r.get("start_bucket") == "july"]
    other = [r for r in rest if r.get("start_bucket") != "july"]
    other.sort(key=lambda r: (r.get("countries") == ["GB"], not r.get("midsize"), r["company"].lower()))
    if july:
        lines.append("## July start")
        lines.extend(_line(r) for r in july)
        lines.append("")
    if other:
        lines.append("## New roles")
        lines.extend(_line(r) for r in other)
        lines.append("")

    body: list[str] = []
    count = 0
    for line in lines:
        if line.startswith("- "):
            if count >= MAX_LINES:
                continue
            count += 1
        body.append(line)
    total = len(new_roles)
    header = f"{total} new role{'s' if total != 1 else ''} on {today}"
    if hits:
        header += f", {len(hits)} watchlist compan{'ies' if len(hits) != 1 else 'y'} just opened"
    footer = []
    shown = count
    all_lines = sum(1 for l in lines if l.startswith("- "))
    if all_lines > shown:
        footer.append(f"_…and {all_lines - shown} more. See the site._")
    footer.append(f"\n[Open the tracker]({SITE_URL})")
    return f"{header}.\n\n" + "\n".join(body).rstrip() + "\n\n" + "\n".join(footer) + "\n"


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
