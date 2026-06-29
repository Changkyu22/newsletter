"""네이버 검색 API 및 Google News RSS 기반 뉴스 수집."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
import requests

from config import (
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    HTTP_TIMEOUT,
    HTTP_VERIFY_SSL,
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    NEWS_HOURS_LOOKBACK,
    NEWS_MAX_PER_KEYWORD,
)
from models import CollectionResult, NewsArticle
from utils import (
    clean_title,
    dedupe_articles,
    is_within_hours,
    logger,
    strip_html,
    summarize_text,
)

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"

MAX_RETRIES = 3
RETRY_DELAY_SEC = 1.5


def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=HTTP_TIMEOUT,
                verify=HTTP_VERIFY_SSL,
            )
            if response.status_code == 429:
                wait = RETRY_DELAY_SEC * attempt
                logger.warning("Rate limit (429) on %s — retry in %.1fs", url, wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC * attempt)
    raise last_error or requests.RequestException(f"Failed to fetch {url}")


def fetch_naver_news(
    keyword: str,
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
    max_results: int = NEWS_MAX_PER_KEYWORD,
) -> tuple[list[NewsArticle], str | None]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return [], "네이버 API 자격 증명이 설정되지 않았습니다."

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": keyword,
        "display": min(max_results * 4, 100),
        "start": 1,
        "sort": "date",
    }

    try:
        response = _request_with_retry("GET", NAVER_NEWS_URL, headers=headers, params=params)
        data = response.json()
    except requests.RequestException as exc:
        msg = f"[네이버] '{keyword}' 수집 실패: {exc}"
        logger.error(msg)
        return [], msg

    articles: list[NewsArticle] = []
    for item in data.get("items", []):
        try:
            pub_date = parsedate_to_datetime(item.get("pubDate", ""))
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue

        if not is_within_hours(pub_date, hours_lookback):
            continue

        raw_desc = item.get("description", "")
        title = clean_title(item.get("title", ""))
        if not title:
            continue

        link = item.get("originallink") or item.get("link", "")
        press = ""
        if link:
            try:
                press = strip_html(link.split("/")[2])
            except IndexError:
                press = ""

        articles.append(
            NewsArticle(
                title=title,
                summary=summarize_text(strip_html(raw_desc) or title),
                link=link,
                source="naver",
                keyword=keyword,
                published_at=pub_date,
                press=press,
            )
        )
        if len(articles) >= max_results:
            break

    return articles, None


def fetch_google_news_rss(
    keyword: str,
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
    max_results: int = NEWS_MAX_PER_KEYWORD,
) -> tuple[list[NewsArticle], str | None]:
    query = quote(f"{keyword} when:{hours_lookback}h")
    url = f"{GOOGLE_NEWS_RSS}?q={query}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        response = _request_with_retry("GET", url)
        feed = feedparser.parse(response.text)
    except requests.RequestException as exc:
        msg = f"[Google RSS] '{keyword}' 수집 실패: {exc}"
        logger.error(msg)
        return [], msg

    articles: list[NewsArticle] = []
    for entry in feed.entries:
        pub_date = None
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    pub_date = datetime(*parsed[:6], tzinfo=timezone.utc)
                    break
                except (TypeError, ValueError):
                    continue

        if pub_date is None:
            pub_date = datetime.now(timezone.utc)

        if not is_within_hours(pub_date, hours_lookback):
            continue

        title = clean_title(entry.get("title", ""))
        if not title:
            continue

        raw_summary = entry.get("summary", entry.get("description", ""))
        source_name = ""
        if entry.get("source") and hasattr(entry.source, "title"):
            source_name = entry.source.title

        articles.append(
            NewsArticle(
                title=title,
                summary=summarize_text(strip_html(raw_summary) or title),
                link=entry.get("link", ""),
                source="google",
                keyword=keyword,
                published_at=pub_date,
                press=source_name,
            )
        )
        if len(articles) >= max_results:
            break

    return articles, None


def fetch_google_news_api(
    keyword: str,
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
    max_results: int = NEWS_MAX_PER_KEYWORD,
) -> tuple[list[NewsArticle], str | None]:
    """Google Custom Search API (선택). RSS 실패 시 대체."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return [], None

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": keyword,
        "dateRestrict": "d1",
        "num": min(max_results * 2, 10),
        "sort": "date",
    }

    try:
        response = _request_with_retry("GET", GOOGLE_CSE_URL, params=params)
        data = response.json()
    except requests.RequestException as exc:
        msg = f"[Google API] '{keyword}' 수집 실패: {exc}"
        logger.error(msg)
        return [], msg

    articles: list[NewsArticle] = []
    for item in data.get("items", []):
        pub_date = datetime.now(timezone.utc)
        pagemap = item.get("pagemap", {})
        metatags = pagemap.get("metatags", [{}])
        for tag in metatags:
            for key in ("article:published_time", "og:updated_time", "date"):
                if key in tag:
                    try:
                        pub_date = datetime.fromisoformat(tag[key].replace("Z", "+00:00"))
                        break
                    except ValueError:
                        continue

        if not is_within_hours(pub_date, hours_lookback):
            continue

        title = clean_title(item.get("title", ""))
        if not title:
            continue

        articles.append(
            NewsArticle(
                title=title,
                summary=summarize_text(item.get("snippet", "") or title),
                link=item.get("link", ""),
                source="google",
                keyword=keyword,
                published_at=pub_date,
                press=item.get("displayLink", ""),
            )
        )
        if len(articles) >= max_results:
            break

    return articles, None


def fetch_news_for_keyword(
    keyword: str,
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
    max_per_keyword: int = NEWS_MAX_PER_KEYWORD,
) -> tuple[list[NewsArticle], list[str]]:
    """키워드별 네이버 + 구글 수집 후 중복 제거, 최신순 상위 N건."""
    errors: list[str] = []
    combined: list[NewsArticle] = []

    naver_articles, naver_err = fetch_naver_news(keyword, hours_lookback, max_per_keyword * 2)
    if naver_err:
        errors.append(naver_err)
    combined.extend(naver_articles)

    google_articles, google_err = fetch_google_news_rss(keyword, hours_lookback, max_per_keyword * 2)
    if google_err:
        google_api_articles, google_api_err = fetch_google_news_api(keyword, hours_lookback, max_per_keyword * 2)
        if google_api_articles:
            combined.extend(google_api_articles)
        elif google_api_err:
            errors.append(google_err)
            errors.append(google_api_err)
        else:
            errors.append(google_err)
    else:
        combined.extend(google_articles)

    deduped = dedupe_articles(combined)
    deduped.sort(key=lambda a: a.published_at, reverse=True)
    return deduped[:max_per_keyword], errors


def collect_all_news(
    keywords: list[str],
    hours_lookback: int = NEWS_HOURS_LOOKBACK,
    max_per_keyword: int = NEWS_MAX_PER_KEYWORD,
) -> CollectionResult:
    """모든 키워드에 대해 뉴스를 수집."""
    if not keywords:
        return CollectionResult(
            errors=["등록된 키워드가 없습니다."],
            fetched_at=datetime.now(timezone.utc),
        )

    all_articles: list[NewsArticle] = []
    all_errors: list[str] = []

    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        try:
            articles, errors = fetch_news_for_keyword(keyword, hours_lookback, max_per_keyword)
            all_articles.extend(articles)
            all_errors.extend(errors)
            logger.info("'%s': %d articles collected", keyword, len(articles))
        except Exception as exc:
            msg = f"'{keyword}' 수집 중 예외: {exc}"
            logger.exception(msg)
            all_errors.append(msg)

    return CollectionResult(
        articles=all_articles,
        errors=all_errors,
        fetched_at=datetime.now(timezone.utc),
    )
