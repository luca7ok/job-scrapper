from tracker import mail
from tracker.notify import build_notification

ROLES = [
    {"id": "a", "company": "Booking.com", "title": "Software Engineer Intern", "url": "https://example.com/a",
     "locations": "Amsterdam", "countries": ["NL"], "start_label": "July 2027", "start_bucket": "july", "midsize": False},
    {"id": "b", "company": "Bolt", "title": "Backend Intern <C++>", "url": "https://example.com/b",
     "locations": "Tallinn", "countries": ["EE"], "start_label": "Summer 2027", "start_bucket": "summer", "midsize": True},
]


def body():
    by_id = {r["id"]: r for r in ROLES}
    return build_notification(ROLES, [{"company": "Bolt", "role_ids": ["b"]}], by_id, "2026-11-10")


def test_email_contains_only_new_roles_as_html_and_text():
    cfg = {"user": "me@gmail.com", "password": "x", "to": "me@gmail.com", "host": "smtp.gmail.com", "port": 465}
    msg = mail.build_message(body(), cfg)
    assert msg["Subject"] == "EU SWE 2027: 2 new roles, 1 watchlist company just opened"
    assert msg["To"] == "me@gmail.com"
    text = msg.get_body(("plain",)).get_content()
    html = msg.get_body(("html",)).get_content()
    assert "Software Engineer Intern <https://example.com/a>" in text
    assert '<a href="https://example.com/a"' in html
    assert "<strong>Booking.com</strong>" in html
    assert "Backend Intern &lt;C++&gt;" in html
    assert "<h3" in html and "Newly opened" in html


class FakeSMTP:
    sent = []

    def __init__(self, host, port, context=None, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        FakeSMTP.sent.append(("login", user, password))

    def send_message(self, msg):
        FakeSMTP.sent.append(("send", msg["To"], msg["Subject"]))


def test_main_sends_with_gmail_app_password(tmp_path, monkeypatch):
    path = tmp_path / "notify.md"
    path.write_text(body())
    monkeypatch.setenv("SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.delenv("EMAIL_TO", raising=False)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", FakeSMTP)
    FakeSMTP.sent = []
    assert mail.main([str(path)]) == 0
    assert FakeSMTP.sent[0] == ("login", "me@gmail.com", "abcdefghijklmnop")
    assert FakeSMTP.sent[1][0] == "send" and FakeSMTP.sent[1][1] == "me@gmail.com"


def test_main_without_settings_or_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert mail.main([str(tmp_path / "missing.md")]) == 0
    path = tmp_path / "notify.md"
    path.write_text(body())
    assert mail.main([str(path)]) == 2


def test_email_to_override(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "bot@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    assert mail.settings()["to"] == "me@example.com"


def test_sample_preview(tmp_path, monkeypatch):
    out = tmp_path / "preview.html"
    assert mail.main(["--sample", "--preview", str(out)]) == 0
    html = out.read_text()
    assert "placeholders" in html and "Example Watchlist Co" in html and "Newly opened" in html
    assert mail.subject_from(mail.sample_body()).startswith("EU SWE 2027: TEST · 5 new roles")


def test_sample_send_requires_settings(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert mail.main(["--sample"]) == 2
