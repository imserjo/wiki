import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import settings


def send_email(to: str, subject: str, html_body: str) -> None:
    """Отправляет HTML-письмо через SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())


def send_password_reset_email(to: str, reset_url: str) -> None:
    subject = "Сброс пароля — База знаний"
    html = f"""
    <h2>Сброс пароля</h2>
    <p>Вы запросили сброс пароля. Перейдите по ссылке:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>Ссылка действительна 1 час. Если вы не запрашивали сброс — просто проигнорируйте это письмо.</p>
    """
    send_email(to, subject, html)