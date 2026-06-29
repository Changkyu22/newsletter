"""키워드·수신자 설정 영속화."""

import json

from config import SETTINGS_FILE

DEFAULT_SETTINGS = {
    "keywords": [],
    "recipients": [],
    "intro": "",
    "custom_title": "",
}


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def add_keyword(keyword: str, settings: dict) -> dict:
    kw = keyword.strip()
    if kw and kw not in settings["keywords"]:
        settings["keywords"].append(kw)
    return settings


def remove_keyword(keyword: str, settings: dict) -> dict:
    settings["keywords"] = [k for k in settings["keywords"] if k != keyword]
    return settings


def add_recipient(email: str, settings: dict) -> dict:
    em = email.strip()
    if em and em not in settings["recipients"]:
        settings["recipients"].append(em)
    return settings


def remove_recipient(email: str, settings: dict) -> dict:
    settings["recipients"] = [e for e in settings["recipients"] if e != email]
    return settings
