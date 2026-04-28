"""SMTP email delivery via Microsoft 365."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587


class MailerError(RuntimeError):
    """Raised when SMTP delivery fails."""


def send(html: str, subject: str, sender_email: str, sender_name: str, recipient: str) -> None:
    smtp_user = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password:
        raise MailerError("SMTP_EMAIL and SMTP_PASSWORD must be set.")

    from_address = sender_email or smtp_user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name or "BSB Morning Brief", from_address))
    msg["To"] = recipient
    msg["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])
    msg.set_content("This newsletter requires an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")

    logger.info("Sending email to %s via %s as %s", recipient, SMTP_HOST, smtp_user)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("SMTP delivery failed.")
        raise MailerError(f"SMTP delivery failed: {exc}") from exc

    logger.info("Email delivered.")
