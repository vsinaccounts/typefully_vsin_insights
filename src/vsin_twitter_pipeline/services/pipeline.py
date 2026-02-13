from datetime import datetime, timezone
from datetime import timedelta
import uuid

from vsin_twitter_pipeline.clients.openai_client import OpenAIClient
from vsin_twitter_pipeline.clients.rss_client import RSSClient
from vsin_twitter_pipeline.clients.typefully_client import TypefullyClient
from vsin_twitter_pipeline.core.logging import get_logger
from vsin_twitter_pipeline.models.schemas import Article
from vsin_twitter_pipeline.services.article_extractor import ArticleExtractor
from vsin_twitter_pipeline.services.content_cleaner import ContentCleaner
from vsin_twitter_pipeline.services.repository import Repository
from typing import Optional

logger = get_logger(__name__)


class PipelineService:
    def __init__(
        self,
        rss_client: RSSClient,
        extractor: ArticleExtractor,
        cleaner: ContentCleaner,
        openai_client: OpenAIClient,
        typefully_client: TypefullyClient,
        repository: Repository,
        max_articles_per_run: int,
        publish_mode: str,
        schedule_iso8601: Optional[str],
        enable_thread_generation: bool,
        min_insights_for_thread: int,
        min_chars_for_thread: int,
        min_autopublish_spacing_minutes: int,
        dry_run: bool,
    ):
        self.rss_client = rss_client
        self.extractor = extractor
        self.cleaner = cleaner
        self.openai_client = openai_client
        self.typefully_client = typefully_client
        self.repository = repository
        self.max_articles_per_run = max_articles_per_run
        self.publish_mode = publish_mode
        self.schedule_iso8601 = schedule_iso8601
        self.enable_thread_generation = enable_thread_generation
        self.min_insights_for_thread = min_insights_for_thread
        self.min_chars_for_thread = min_chars_for_thread
        self.min_autopublish_spacing_minutes = min_autopublish_spacing_minutes
        self.dry_run = dry_run
        self._publish_cursor: Optional[datetime] = None

    def run_once(self) -> dict:
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        run_row_id = self.repository.create_run(run_id=run_id)

        found = 0
        processed = 0
        failed = 0

        logger.info("pipeline started", extra={"event": "pipeline_start", "run_id": run_id})

        try:
            if self.publish_mode == "schedule" and not self.schedule_iso8601:
                self._publish_cursor = self.typefully_client.get_latest_scheduled_publish_at()
            entries = self.rss_client.fetch_entries()
            for entry in entries[: self.max_articles_per_run]:
                found += 1
                article_id = entry["article_id"]

                if self.repository.is_processed(article_id):
                    logger.info(
                        "article already processed",
                        extra={"event": "skip_duplicate", "article_id": article_id, "run_id": run_id},
                    )
                    continue

                try:
                    clean_text = self._extract_and_clean(entry["url"], entry.get("feed_content", ""))
                    insights = self.cleaner.extract_key_points(clean_text)
                    article = Article(
                        article_id=article_id,
                        title=entry["title"],
                        author=entry.get("author"),
                        url=entry["url"],
                        published_at=entry.get("published_at"),
                        raw_html=entry.get("feed_content", ""),
                        clean_text=clean_text,
                        extracted_insights=insights,
                    )

                    allow_thread = self._allow_thread_for_article(clean_text, insights)
                    tweets = self.openai_client.generate_tweets(article, allow_thread)

                    if self.dry_run:
                        logger.info(
                            "dry run: skipped typefully publish",
                            extra={"event": "typefully_skip", "article_id": article_id, "run_id": run_id},
                        )
                    else:
                        effective_mode = self.publish_mode
                        effective_schedule = self._resolve_schedule_for_next_post()

                        if tweets.delivery_mode == "thread":
                            thread_draft = self.typefully_client.create_thread(
                                tweets=tweets.thread,
                                mode=effective_mode,
                                schedule_at=effective_schedule,
                            )
                            self.repository.record_draft(
                                article_id=article_id,
                                draft_type="thread",
                                payload={"thread": tweets.thread},
                                publish_mode=effective_mode,
                                status=thread_draft.status,
                                remote_id=thread_draft.remote_id,
                            )
                        else:
                            single_payload = {"single_tweet": tweets.single_tweet}
                            single_draft = self.typefully_client.create_single(
                                content=tweets.single_tweet,
                                mode=effective_mode,
                                schedule_at=effective_schedule,
                            )
                            self.repository.record_draft(
                                article_id=article_id,
                                draft_type="single",
                                payload=single_payload,
                                publish_mode=effective_mode,
                                status=single_draft.status,
                                remote_id=single_draft.remote_id,
                            )

                    self.repository.mark_processed(
                        article_id=article_id,
                        url=entry["url"],
                        title=entry["title"],
                        published_at=entry.get("published_at"),
                    )

                    processed += 1
                    logger.info(
                        "article processed",
                        extra={"event": "article_processed", "article_id": article_id, "run_id": run_id},
                    )
                except Exception as exc:
                    failed += 1
                    logger.exception(
                        "article processing failed",
                        extra={
                            "event": "article_failed",
                            "article_id": article_id,
                            "run_id": run_id,
                            "error": str(exc),
                        },
                    )

            status = "completed" if failed == 0 else "completed_with_errors"
            self.repository.finalize_run(
                run_row_id=run_row_id,
                status=status,
                articles_found=found,
                articles_processed=processed,
                articles_failed=failed,
            )

            summary = {
                "run_id": run_id,
                "status": status,
                "articles_found": found,
                "articles_processed": processed,
                "articles_failed": failed,
            }
            logger.info("pipeline complete", extra={"event": "pipeline_complete", "run_id": run_id, "status": status})
            return summary
        except Exception:
            self.repository.finalize_run(
                run_row_id=run_row_id,
                status="failed",
                articles_found=found,
                articles_processed=processed,
                articles_failed=failed + 1,
            )
            raise

    def _extract_and_clean(self, url: str, feed_content: str) -> str:
        article_text = self.extractor.fetch_article_text(url, rss_content=feed_content)
        clean_text = self.cleaner.clean(article_text)
        return clean_text

    def _allow_thread_for_article(self, clean_text: str, insights: list[str]) -> bool:
        if not self.enable_thread_generation:
            return False

        # Single-tweet mode is default. Threads are only enabled for deep, data-rich articles.
        return len(insights) >= self.min_insights_for_thread and len(clean_text) >= self.min_chars_for_thread

    def _resolve_schedule_for_next_post(self) -> Optional[str]:
        if self.publish_mode != "schedule":
            return self.schedule_iso8601

        if self.schedule_iso8601:
            return self.schedule_iso8601

        # Always audit Typefully queue before assigning the next scheduled time.
        latest_remote = self.typefully_client.get_latest_scheduled_publish_at()
        if latest_remote and (not self._publish_cursor or latest_remote > self._publish_cursor):
            self._publish_cursor = latest_remote

        now_utc = datetime.now(timezone.utc)
        if self._publish_cursor and self._publish_cursor.tzinfo is None:
            self._publish_cursor = self._publish_cursor.replace(tzinfo=timezone.utc)

        if not self._publish_cursor:
            scheduled = now_utc
        else:
            scheduled = self._publish_cursor + timedelta(minutes=self.min_autopublish_spacing_minutes)
            if scheduled < now_utc:
                scheduled = now_utc

        self._publish_cursor = scheduled
        return scheduled.isoformat().replace("+00:00", "Z")
