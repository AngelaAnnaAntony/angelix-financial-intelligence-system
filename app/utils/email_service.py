import logging
import os
import smtplib
from email.message import EmailMessage

from flask import current_app


logger = logging.getLogger(__name__)


def send_email(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> bool:
    """
    Send a plain-text email using the configured SMTP server.

    Returns:
        True  -> email sent successfully
        False -> email delivery failed
    """

    smtp_host = current_app.config.get("MAIL_SERVER", "")
    smtp_port = int(
        current_app.config.get("MAIL_PORT", 587)
    )
    smtp_username = current_app.config.get(
        "MAIL_USERNAME",
        "",
    )
    smtp_password = current_app.config.get(
        "MAIL_PASSWORD",
        "",
    )
    smtp_use_tls = current_app.config.get(
        "MAIL_USE_TLS",
        True,
    )
    smtp_use_ssl = current_app.config.get(
        "MAIL_USE_SSL",
        False,
    )
    sender = current_app.config.get(
        "MAIL_DEFAULT_SENDER",
        smtp_username,
    )

    if not smtp_host:
        logger.error(
            "Email delivery failed: MAIL_SERVER is not configured."
        )
        return False

    if not sender:
        logger.error(
            "Email delivery failed: MAIL_DEFAULT_SENDER "
            "or MAIL_USERNAME is not configured."
        )
        return False

    try:
        message = EmailMessage()

        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient

        message.set_content(body)

        if smtp_use_ssl:
            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=30,
            ) as server:

                if smtp_username and smtp_password:
                    server.login(
                        smtp_username,
                        smtp_password,
                    )

                server.send_message(message)

        else:
            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=30,
            ) as server:

                server.ehlo()

                if smtp_use_tls:
                    server.starttls()
                    server.ehlo()

                if smtp_username and smtp_password:
                    server.login(
                        smtp_username,
                        smtp_password,
                    )

                server.send_message(message)

        logger.info(
            "Email sent successfully to %s",
            recipient,
        )

        return True

    except Exception:
        logger.exception(
            "Email delivery failed for recipient %s",
            recipient,
        )

        return False


def send_password_reset_email(
    *,
    recipient: str,
    reset_url: str,
    expiry_minutes: int = 30,
) -> bool:
    """
    Send an Angelix password-reset email.
    """

    subject = "Angelix - Password Reset"

    body = f"""Hello,

We received a request to reset the password for your Angelix account.

Use the link below to reset your password:

{reset_url}

This link will expire in {expiry_minutes} minutes and can only be used once.

If you did not request a password reset, you can safely ignore this email.

For security reasons, please do not share this link with anyone.

Regards,
Angelix Team
AI-Powered Financial Intelligence Platform
"""

    return send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )