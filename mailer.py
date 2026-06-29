"""SMTP 기반 뉴스레터 이메일 발송."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    NEWS_HOURS_LOOKBACK,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SENDER_EMAIL,
    SMTP_SENDER_NAME,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)
from models import NewsArticle
from templates import build_html_body, build_newsletter_title, build_plain_body
from utils import logger


class MailerError(Exception):
    """메일 발송 관련 오류."""


def validate_smtp_config() -> tuple[bool, str]:
    if not SMTP_HOST:
        return False, "SMTP_HOST가 설정되지 않았습니다."
    if not SMTP_SENDER_EMAIL:
        return False, "SMTP_SENDER_EMAIL이 설정되지 않았습니다."
    return True, "SMTP 설정 완료"


def build_newsletter_content(
    articles: list[NewsArticle],
    keywords: list[str],
    *,
    title: str = "",
    intro: str = "",
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
) -> tuple[str, str, str]:
    """(subject, html_body, plain_body) 반환."""
    subject = build_newsletter_title(keywords, title)
    html_body = build_html_body(articles, keywords, hours_lookback, subject, intro)
    plain_body = build_plain_body(articles, keywords, hours_lookback, intro)
    return subject, html_body, plain_body


def send_email(
    to_emails: list[str],
    subject: str,
    html_body: str,
    plain_body: str,
) -> None:
    """수신자 목록에 HTML/Plain 멀티파트 메일 발송."""
    recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        raise MailerError("수신자 이메일이 없습니다.")

    ok, message = validate_smtp_config()
    if not ok:
        raise MailerError(message)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_SENDER_NAME} <{SMTP_SENDER_EMAIL}>"
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER_EMAIL, recipients, msg.as_string())
        logger.info("Email sent to %d recipient(s): %s", len(recipients), ", ".join(recipients))
    except smtplib.SMTPAuthenticationError as exc:
        msg_err = f"SMTP 인증 실패: {exc}"
        logger.error(msg_err)
        raise MailerError(msg_err) from exc
    except smtplib.SMTPException as exc:
        msg_err = f"SMTP 발송 오류: {exc}"
        logger.error(msg_err)
        raise MailerError(msg_err) from exc
    except OSError as exc:
        msg_err = f"SMTP 연결 실패 ({SMTP_HOST}:{SMTP_PORT}): {exc}"
        logger.error(msg_err)
        raise MailerError(msg_err) from exc


def send_newsletter(
    articles: list[NewsArticle],
    keywords: list[str],
    recipient_emails: list[str],
    *,
    title: str = "",
    intro: str = "",
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
) -> dict:
    """뉴스레터 본문 생성 후 발송. 결과 dict 반환."""
    subject, html_body, plain_body = build_newsletter_content(
        articles, keywords, title=title, intro=intro, hours_lookback=hours_lookback
    )

    try:
        send_email(recipient_emails, subject, html_body, plain_body)
        return {
            "success": True,
            "message": f"{len(recipient_emails)}명에게 발송 완료",
            "subject": subject,
            "html_body": html_body,
            "plain_body": plain_body,
            "article_count": len(articles),
        }
    except MailerError as exc:
        return {
            "success": False,
            "message": str(exc),
            "subject": subject,
            "html_body": html_body,
            "plain_body": plain_body,
            "article_count": len(articles),
        }
