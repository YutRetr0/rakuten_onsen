import os
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.utils import formataddr

log = logging.getLogger(__name__)

def notify(channels, title, body, url=""):
    for ch in channels:
        try:
            handler = {
                "telegram":   _telegram,
                "email":      _email,
                "webhook":    _webhook,
                "bark":       _bark,
                "wecom":      _wecom_bot,
                "serverchan": _serverchan,
                "pushplus":   _pushplus,
            }.get(ch)
            if handler:
                handler(title, body, url)
            else:
                log.warning("unknown channel: %s", ch)
        except Exception as e:
            log.exception("notify %s failed: %s", ch, e)


def _wecom_bot(title, body, url):
    hook = os.getenv("WECOM_BOT_WEBHOOK")
    if not hook:
        return log.warning("wecom bot not configured")
    md = f"## {title}\n\n{body}"
    if url:
        md += f"\n\n[View]({url})"
    r = requests.post(
        hook,
        json={"msgtype": "markdown", "markdown": {"content": md}},
        timeout=10,
    )
    r.raise_for_status()


def _serverchan(title, body, url):
    key = os.getenv("SERVERCHAN_KEY")
    if not key:
        return log.warning("serverchan not configured")
    desp = body + (f"\n\n[View]({url})" if url else "")
    r = requests.post(
        f"https://sctapi.ftqq.com/{{key}}.send",
        data={"title": title, "desp": desp},
        timeout=10,
    )
    r.raise_for_status()


def _pushplus(title, body, url):
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        return log.warning("pushplus not configured")
    content = body + (f"\n\n[View]({url})" if url else "")
    r = requests.post(
        "http://www.pushplus.plus/send",
        json={"token": token, "title": title,
              "content": content, "template": "markdown"},
        timeout=10,
    )
    r.raise_for_status()


def _telegram(title, body, url):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return log.warning("telegram not configured")
    text = f"*{{title}}*\n\n{{body}}"
    if url:
        text += f"\n\n[View]({url})"
    r = requests.post(
        f"https://api.telegram.org/bot{{token}}/sendMessage",
        json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    r.raise_for_status()


def _email(title, body, url):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 465))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    to = os.getenv("EMAIL_TO")
    if not all([host, user, pwd, to]):
        return log.warning("smtp not configured")
    full = body + (f"\n\n{{url}}" if url else "")
    msg = MIMEText(full, "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = formataddr(("Onsen Watcher", user))
    msg["To"] = to
    with smtplib.SMTP_SSL(host, port, timeout=15) as s:
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())


def _webhook(title, body, url):
    hook = os.getenv("WEBHOOK_URL")
    if not hook:
        return log.warning("webhook not configured")
    r = requests.post(
        hook,
        json={"title": title, "body": body, "url": url},
        timeout=10,
    )
    r.raise_for_status()


def _bark(title, body, url):
    key = os.getenv("BARK_KEY")
    if not key:
        return log.warning("bark not configured")
    r = requests.post(
        f"https://api.day.app/{{key}}",
        json={"title": title, "body": body, "url": url},
        timeout=10,
    )
    r.raise_for_status()