"""
Email service for sending debrief summaries with audio attachments.
"""

import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from app.config import settings


async def send_debrief_email(
    recipient: str,
    subject: str,
    summary_text: str,
    audio_bytes: bytes,
) -> bool:
    """
    Send debrief email with audio attachment via Gmail SMTP.

    Returns True if successful, False otherwise.
    """
    if not settings.email_enabled:
        print("Email not configured (missing SMTP credentials)")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject

        # Add summary text as body
        msg.attach(MIMEText(summary_text, "plain"))

        # Add audio as attachment
        if audio_bytes:
            audio_part = MIMEBase("audio", "mpeg")
            audio_part.set_payload(audio_bytes)
            encoders.encode_base64(audio_part)
            audio_part.add_header(
                "Content-Disposition",
                f"attachment; filename= weekly_debrief.mp3",
            )
            msg.attach(audio_part)

        # Send via Gmail SMTP
        def send_smtp():
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

        await asyncio.to_thread(send_smtp)
        print(f"✓ Debrief email sent to {recipient}")
        return True

    except Exception as e:
        print(f"Failed to send debrief email: {e}")
        return False
