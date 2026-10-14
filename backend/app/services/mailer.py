"""Outgoing email over SMTP (stdlib smtplib): sign-up confirmation and password reset links.

Without SMTP_HOST nothing is sent: the message is printed to the server console instead, which is
enough on a single machine (copy the link from the terminal). See docs/configuration.md.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.core import config


def configured() -> bool:
    return bool(config.SMTP_HOST)


def send(to: str, subject: str, body: str) -> None:
    """Blocking; call it from a background task so the response time does not depend on it."""
    if not configured():
        print(f"--- Email (SMTP_HOST is empty, not sent) ---\nTo: {to}\nSubject: {subject}\n\n{body}\n---", flush=True)
        return
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM or config.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context()
    try:
        if config.SMTP_SECURITY == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=20)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
        with server:
            if config.SMTP_SECURITY == "starttls":
                server.starttls(context=context)
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        # The page already told the user to check their inbox; the admin sees why nothing arrived.
        print(f"!! Email to {to} failed: {e}", flush=True)
