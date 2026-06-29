"""데이터 모델."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class NewsArticle:
    title: str
    summary: str
    link: str
    source: Literal["naver", "google"]
    keyword: str
    published_at: datetime
    press: str = ""


@dataclass
class CollectionResult:
    articles: list[NewsArticle] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 or len(self.articles) > 0
