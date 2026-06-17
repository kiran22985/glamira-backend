import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("glamira.email")


def send_password_reset_email(to_email: str, code: str) -> None:
    """Email a one-time reset code, or log it to the console if SMTP isn't
    configured.

    Kept synchronous and called from a background task so a slow/broken mail
    server never blocks or fails the API response.
    """
    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured — password reset code for %s: %s", to_email, code
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Glamira password reset code"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        "We received a request to reset your Glamira password.\n\n"
        f"Your reset code is: {code}\n\n"
        f"It expires in {settings.reset_token_expire_minutes} minutes. "
        "If you didn't request this, you can safely ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception:  # noqa: BLE001 - never surface mail errors to the client
        logger.exception("Failed to send password reset email to %s", to_email)
