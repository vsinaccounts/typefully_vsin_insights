from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    article_id: str
    title: str
    author: Optional[str]
    url: str
    published_at: Optional[datetime]
    raw_html: str
    clean_text: str
    extracted_insights: list[str]


@dataclass
class TweetPackage:
    delivery_mode: str
    single_tweet: str
    thread: list[str]


@dataclass
class DraftResult:
    remote_id: str
    status: str
