from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser


def html_to_text(raw: str | None, limit: int | None = None) -> str:
    if not raw:
        return ""
    s = raw
    if "&lt;" in s and "<" not in s[:200]:
        s = html.unescape(s)
    try:
        tree = HTMLParser(s)
        for tag in tree.css("script, style"):
            tag.decompose()
        body = tree.body or tree.root
        text = body.text(separator="\n") if body is not None else s
    except Exception:
        text = re.sub(r"<[^>]+>", " ", s)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:limit] if limit else text


def iso_from_unix(ts: float | int | None) -> str | None:
    if ts is None:
        return None
    try:
        ts = float(ts)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def iso_from_string(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else None


def iso_days_ago(days: int, today: date) -> str:
    return (today - timedelta(days=days)).isoformat()


def nice_case(s: str) -> str:
    s = (s or "").strip()
    if s and s == s.lower():
        small = {"and", "of", "the", "for", "in", "at", "de", "la", "le", "von", "van", "der"}
        words = s.split(" ")
        out = []
        for i, w in enumerate(words):
            if i > 0 and w in small:
                out.append(w)
            elif len(w) <= 3 and w.isalpha() and w in {"ai", "ml", "it", "qa", "ui", "ux", "sre", "swe", "sde", "ios", "phd", "r&d", "hr"}:
                out.append({"ios": "iOS", "phd": "PhD"}.get(w, w.upper()))
            else:
                out.append(w[:1].upper() + w[1:])
        return " ".join(out)
    return s


def sentence_case(s: str) -> str:
    s = (s or "").strip()
    if s and s == s.lower():
        fixed = re.sub(r"\b(ai|ml|swe|sde|sre|qa|ui|ux|api|aws|gpu|llm|nlp|it)\b", lambda m: m.group(1).upper(), s)
        fixed = re.sub(r"\bios\b", "iOS", fixed)
        fixed = re.sub(r"\bphd\b", "PhD", fixed)
        return fixed[:1].upper() + fixed[1:]
    return s
