"""SMTP email delivery. Supports Gmail (default) and Microsoft 365."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

logger = logging.getLogger(__name__)

# Defaults to Gmail.  Override with SMTP_HOST / SMTP_PORT env vars to use
# another provider (e.g. smtp.office365.com:587).
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587


class MailerError(RuntimeError):
    """Raised when SMTP delivery fails."""


def send(html: str, subject: str, sender_email: str, sender_name: str, recipient: str) -> None:
    smtp_user = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password:
        raise MailerError("SMTP_EMAIL and SMTP_PASSWORD must be set.")

    smtp_host = os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST)
    smtp_port = int(os.getenv("SMTP_PORT", str(DEFAULT_SMTP_PORT)))

    # For Gmail the From address must match the authenticated account.
    from_address = smtp_user if "gmail" in smtp_host else (sender_email or smtp_user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name or "BSB Morning Brief", from_address))
    msg["To"] = recipient
    msg["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])
    msg.set_content("This newsletter requires an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")

    logger.info("Sending email to %s via %s:%d as %s", recipient, smtp_host, smtp_port, smtp_user)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("SMTP delivery failed.")
        raise MailerError(f"SMTP delivery failed: {exc}") from exc

    logger.info("Email delivered.")
