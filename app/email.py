import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.database import get_settings

logger = logging.getLogger(__name__)


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP não configurado — e-mail não enviado para %s", destinatario)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = destinatario
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], destinatario, msg.as_string())
        logger.info("E-mail enviado para %s: %s", destinatario, assunto)
        return True
    except Exception:
        logger.exception("Falha ao enviar e-mail para %s", destinatario)
        return False
