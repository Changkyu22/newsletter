"""환경 변수 및 애플리케이션 설정."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

load_dotenv(BASE_DIR / ".env")

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in ("1", "true", "yes", "on")


# 네이버 검색 API
NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")

# Google (RSS는 키 불필요, Custom Search API는 선택)
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID: str = os.getenv("GOOGLE_CSE_ID", "")

# SMTP
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER_EMAIL: str = os.getenv("SMTP_SENDER_EMAIL", "")
SMTP_SENDER_NAME: str = os.getenv("SMTP_SENDER_NAME", "Hanwha Newsletter")
SMTP_USE_TLS: bool = _bool_env("SMTP_USE_TLS", True)

# 뉴스 수집
NEWS_HOURS_LOOKBACK: int = int(os.getenv("NEWS_HOURS_LOOKBACK", "24"))
NEWS_MAX_PER_KEYWORD: int = int(os.getenv("NEWS_MAX_PER_KEYWORD", "5"))
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "15"))
HTTP_VERIFY_SSL: bool = _bool_env("HTTP_VERIFY_SSL", True)

# 스케줄 (매일 08:00, Asia/Seoul)
SCHEDULE_HOUR: int = int(os.getenv("SCHEDULE_HOUR", "8"))
SCHEDULE_MINUTE: int = int(os.getenv("SCHEDULE_MINUTE", "0"))
SCHEDULE_TIMEZONE: str = os.getenv("SCHEDULE_TIMEZONE", "Asia/Seoul")

SETTINGS_FILE = DATA_DIR / "settings.json"


def credential_status() -> dict[str, bool]:
    """사이드바용 API/SMTP 설정 상태."""
    return {
        "naver": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET),
        "google_rss": True,
        "google_api": bool(GOOGLE_API_KEY and GOOGLE_CSE_ID),
        "smtp": bool(SMTP_HOST and SMTP_SENDER_EMAIL),
    }
