import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import quote

from app.core.config import settings


def send_task_created_email(
    user_email: str,
    title: str,
    description: str,
    priority: str,
    due_date: datetime,
):
    sender_email = settings.GMAIL_EMAIL
    password = settings.GMAIL_APP_PASSWORD

    # -----------------------------
    # Google Calendar Link
    # -----------------------------
    start = due_date.strftime("%Y%m%dT%H%M%S")
    end = due_date.strftime("%Y%m%dT%H%M%S")

    calendar_url = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(title)}"
        f"&details={quote(description or '')}"
        f"&dates={start}/{end}"
    )

    html = f"""
    <html>

    <body style="font-family:Arial">

        <h2>Mission Control</h2>

        <p>Your task has been created successfully.</p>

        <table cellpadding="8">

        <tr>
            <td><b>Task</b></td>
            <td>{title}</td>
        </tr>

        <tr>
            <td><b>Description</b></td>
            <td>{description}</td>
        </tr>

        <tr>
            <td><b>Priority</b></td>
            <td>{priority}</td>
        </tr>

        <tr>
            <td><b>Deadline</b></td>
            <td>{due_date.strftime("%d %B %Y %I:%M %p")}</td>
        </tr>

        </table>

        <br>

        <a href="{calendar_url}"
        style="
        background:#4f46e5;
        color:white;
        padding:12px 20px;
        text-decoration:none;
        border-radius:8px;
        ">
        📅 Add to Google Calendar
        </a>

    </body>

    </html>
    """

    msg = MIMEMultipart()

    msg["From"] = f"Mission Control <{sender_email}>"
    msg["To"] = user_email
    msg["Subject"] = f"Task Created - {title}"

    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.send_message(msg)