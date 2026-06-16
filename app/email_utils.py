import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("glamira.email")


def _build_reset_link(raw_token: str) -> str:
    sep = "&" if "?" in settings.reset_link_base_url else "?"
    return f"{settings.reset_link_base_url}{sep}token={raw_token}"


def send_password_reset_email(to_email: str, raw_token: str) -> None:
    """Send a reset link, or log it to the console if SMTP isn't configured.

    Kept synchronous and called from a background task so a slow/broken mail
    server never blocks or fails the API response.
    """
    link = _build_reset_link(raw_token)

    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured — password reset link for %s: %s", to_email, link
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Reset your Glamira password"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        "We received a request to reset your Glamira password.\n\n"
        f"Use this link to choose a new password:\n{link}\n\n"
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
