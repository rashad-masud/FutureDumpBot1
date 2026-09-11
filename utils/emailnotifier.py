import os
import smtplib
from email.mime.text import MIMEText
from config.settings import ENABLE_EMAIL, EMAIL_COOLDOWN_SECONDS


def send_email(subject, body, symbol=None, cooldown_seconds=None):
    if not ENABLE_EMAIL:
        return

    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", username or "")
    server_name = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    server_port = int(os.getenv("SMTP_PORT", "587"))

    if not username or not password or not recipient:
        print("[EMAIL] Missing SMTP environment variables; notification skipped")
        return

    try:
        msg = MIMEText(body, "plain")
        msg["From"] = username
        msg["To"] = recipient
        msg["Subject"] = subject
        with smtplib.SMTP(server_name, server_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        print("[EMAIL] Sent.")
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
