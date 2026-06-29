"""공통 유틸리티."""

import logging
import re
from datetime import datetime, timedelta, timezone
from html import unescape

from config import LOG_DIR

LOG_FILE = LOG_DIR / "newsletter.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("newsletter")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


logger = setup_logging()


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_title(title: str) -> str:
    return strip_html(title).replace("...", "").strip()


def is_within_hours(published_at: datetime, hours: int) -> bool:
    """발송 시점 기준 지난 N시간 이내 기사인지 확인."""
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(hours=hours)
    return published_at >= cutoff


def normalize_link(link: str) -> str:
    return link.split("&")[0].rstrip("/") if link else link


def dedupe_articles(articles: list) -> list:
    seen: set[str] = set()
    unique = []
    for article in articles:
        key = normalize_link(article.link)
        title_key = re.sub(r"\s+", "", article.title.lower())[:80]
        dedupe_key = f"{key}|{title_key}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique.append(article)
    return unique


def summarize_text(text: str, max_sentences: int = 2, max_chars: int = 200) -> str:
    text = strip_html(text)
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?…])\s+|(?<=다\.)\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return text[:max_chars] + ("..." if len(text) > max_chars else "")

    summary = " ".join(sentences[:max_sentences])
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary
