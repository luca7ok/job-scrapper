from __future__ import annotations

import html
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path

from .notify import build_notification

SAMPLE_ROLES = [
    {"id": "s1", "company": "Example Watchlist Co", "title": "Software Engineering Intern (Summer 2027)", "url": "https://example.com/jobs/1",
     "locations": "Tallinn, Estonia", "countries": ["EE"], "start_label": "June – August 2027", "start_bucket": "july", "midsize": True},
    {"id": "s2", "company": "Placeholder Systems", "title": "Backend Engineer Intern", "url": "https://example.com/jobs/2",
     "locations": "Amsterdam, Netherlands", "countries": ["NL"], "start_label": "July 2027", "start_bucket": "july", "midsize": True},
    {"id": "s3", "company": "Sample Fintech", "title": "Graduate Software Engineer 2027", "url": "https://example.com/jobs/3",
     "locations": "Berlin, Germany; Munich, Germany", "countries": ["DE"], "start_label": "September 2027", "start_bucket": "other", "midsize": False},
    {"id": "s4", "company": "Demo Robotics", "title": "Embedded Software Intern", "url": "https://example.com/jobs/4",
     "locations": "Zurich, Switzerland", "countries": ["CH"], "start_label": "Summer 2027", "start_bucket": "summer", "midsize": True},
    {"id": "s5", "company": "Test Labs", "title": "Junior Frontend Developer", "url": "https://example.com/jobs/5",
     "locations": "Kraków, Poland", "countries": ["PL"], "start_label": "Not stated", "start_bucket": "none", "midsize": False},
]


def sample_body() -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    hits = [{"company": "Example Watchlist Co", "role_ids": ["s1"]}]
    body = build_notification(SAMPLE_ROLES, hits, {r["id"]: r for r in SAMPLE_ROLES}, today)
    return "**Test email: these roles are placeholders, not real postings.**\n\n" + body

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])_(.+?)_(?![\w*])")


def settings() -> dict | None:
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not user or not password:
        return None
    return {
        "user": user,
        "password": password.replace(" ", ""),
        "to": os.environ.get("EMAIL_TO", "").strip() or user,
        "host": os.environ.get("SMTP_HOST", "").strip() or "smtp.gmail.com",
        "port": int(os.environ.get("SMTP_PORT", "").strip() or 465),
    }


def subject_from(body: str) -> str:
    lines = [l for l in body.strip().splitlines() if l.strip() and not l.startswith("**Test email")]
    first = lines[0].rstrip(".") if lines else "New roles"
    if body.startswith("**Test email"):
        first = "TEST · " + first
    first = re.sub(r"\s+on \d{4}-\d{2}-\d{2}", "", first)
    return f"EU SWE 2027: {first}"


def _inline_html(text: str) -> str:
    out = html.escape(text, quote=False)
    out = _LINK.sub(lambda m: f'<a href="{html.escape(m.group(2))}" style="color:#7C3AED">{m.group(1)}</a>', out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    return out


def to_html(body: str) -> str:
    parts: list[str] = []
    in_list = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- "):
            if not in_list:
                parts.append('<ul style="padding-left:18px;margin:6px 0 14px">')
                in_list = True
            parts.append(f'<li style="margin:4px 0">{_inline_html(s[2:])}</li>')
            continue
        if in_list:
            parts.append("</ul>")
            in_list = False
        if not s:
            continue
        if s.startswith("## "):
            parts.append(f'<h3 style="font-size:15px;margin:18px 0 4px">{_inline_html(s[3:])}</h3>')
        else:
            parts.append(f'<p style="margin:8px 0">{_inline_html(s)}</p>')
    if in_list:
        parts.append("</ul>")
    return (
        '<div style="font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;'
        'font-size:14px;line-height:1.5;color:#1F1630;max-width:680px">' + "\n".join(parts) + "</div>"
    )


def to_text(body: str) -> str:
    text = _LINK.sub(lambda m: f"{m.group(1)} <{m.group(2)}>", body)
    text = _BOLD.sub(r"\1", text)
    text = _ITALIC.sub(r"\1", text)
    return re.sub(r"^## ", "", text, flags=re.M)


def build_message(body: str, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject_from(body)
    msg["From"] = f"EU SWE 2027 tracker <{cfg['user']}>"
    msg["To"] = cfg["to"]
    msg.set_content(to_text(body))
    msg.add_alternative(to_html(body), subtype="html")
    return msg


def send(body: str, cfg: dict) -> None:
    msg = build_message(body, cfg)
    context = ssl.create_default_context()
    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=30) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            server.starttls(context=context)
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    sample = "--sample" in args
    preview = None
    if "--preview" in args:
        i = args.index("--preview")
        preview = Path(args[i + 1]) if i + 1 < len(args) else Path("email-preview.html")
        del args[i:i + 2]
    args = [a for a in args if a != "--sample"]
    if sample:
        body = sample_body()
    else:
        path = Path(args[0] if args else "data/notify.md")
        if not path.exists():
            print(f"{path} not found: nothing new, no email sent")
            return 0
        body = path.read_text(encoding="utf-8")
    if preview is not None:
        preview.write_text(f"<!doctype html><meta charset=utf-8><title>{html.escape(subject_from(body))}</title>" + to_html(body), encoding="utf-8")
        print(f"preview written to {preview} (subject: {subject_from(body)})")
        return 0
    cfg = settings()
    if cfg is None:
        print("SMTP_USER / SMTP_PASSWORD not set: email skipped")
        return 2
    try:
        send(body, cfg)
    except Exception as exc:
        print(f"email failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"email sent to {cfg['to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
