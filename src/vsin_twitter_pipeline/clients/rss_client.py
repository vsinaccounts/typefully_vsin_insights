import hashlib
from datetime import datetime
from typing import Optional

import feedparser
from dateutil import parser as date_parser


class RSSClient:
    def __init__(self, feed_url: str, user_agent: str):
        self.feed_url = feed_url
        self.user_agent = user_agent

    def fetch_entries(self) -> list[dict]:
        feed = feedparser.parse(self.feed_url, agent=self.user_agent)
        entries: list[dict] = []

        for e in feed.entries:
            article_id_source = getattr(e, "id", None) or getattr(e, "guid", None) or e.link
            article_id = hashlib.sha256(article_id_source.encode("utf-8")).hexdigest()
            published_at = self._parse_date(getattr(e, "published", None) or getattr(e, "updated", None))
            content = ""
            if getattr(e, "content", None):
                content = "\n".join(item.value for item in e.content if hasattr(item, "value"))
            elif getattr(e, "summary", None):
                content = e.summary

            entries.append(
                {
                    "article_id": article_id,
                    "title": getattr(e, "title", "").strip(),
                    "author": getattr(e, "author", None),
                    "url": getattr(e, "link", "").strip(),
                    "published_at": published_at,
                    "feed_content": content,
                }
            )

        return entries

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return date_parser.parse(value)
        except Exception:
            return None
