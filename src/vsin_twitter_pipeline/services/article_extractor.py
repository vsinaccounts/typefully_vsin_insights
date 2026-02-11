import re

import trafilatura
from bs4 import BeautifulSoup

from vsin_twitter_pipeline.clients.http_client import HTTPClient
from typing import Optional


class ArticleExtractor:
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client

    def fetch_article_text(self, url: str, rss_content: Optional[str] = None) -> str:
        if rss_content and len(self._strip_tags(rss_content)) > 500:
            return rss_content

        html = self.http_client.get_text(url)

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
        if extracted and len(extracted) > 500:
            return extracted

        soup = BeautifulSoup(html, "lxml")
        for selector in ["script", "style", "nav", "header", "footer", "aside", ".menu", ".ad"]:
            for node in soup.select(selector):
                node.decompose()

        article = soup.select_one("article")
        if article:
            return article.get_text("\n", strip=True)

        return soup.get_text("\n", strip=True)

    @staticmethod
    def _strip_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)
