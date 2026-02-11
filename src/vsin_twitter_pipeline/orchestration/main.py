import json
from datetime import datetime, timezone

from vsin_twitter_pipeline.clients.http_client import HTTPClient
from vsin_twitter_pipeline.clients.openai_client import OpenAIClient
from vsin_twitter_pipeline.clients.rss_client import RSSClient
from vsin_twitter_pipeline.clients.typefully_client import TypefullyClient
from vsin_twitter_pipeline.core.config import settings
from vsin_twitter_pipeline.core.logging import setup_logging
from vsin_twitter_pipeline.models.db import Database
from vsin_twitter_pipeline.services.article_extractor import ArticleExtractor
from vsin_twitter_pipeline.services.content_cleaner import ContentCleaner
from vsin_twitter_pipeline.services.pipeline import PipelineService
from vsin_twitter_pipeline.services.repository import Repository


def build_pipeline() -> PipelineService:
    db = Database(settings.database_url)
    db.init()

    repository = Repository(db)
    http_client = HTTPClient(timeout_seconds=settings.request_timeout_seconds, user_agent=settings.user_agent)
    rss_client = RSSClient(feed_url=settings.rss_feed_url, user_agent=settings.user_agent)
    extractor = ArticleExtractor(http_client=http_client)
    cleaner = ContentCleaner()
    openai_client = OpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_output_tokens=settings.openai_max_output_tokens,
    )
    typefully_client = TypefullyClient(
        api_base=settings.typefully_api_base,
        api_key=settings.typefully_api_key,
        social_set_id=settings.typefully_social_set_id,
        timeout_seconds=settings.request_timeout_seconds,
    )

    return PipelineService(
        rss_client=rss_client,
        extractor=extractor,
        cleaner=cleaner,
        openai_client=openai_client,
        typefully_client=typefully_client,
        repository=repository,
        max_articles_per_run=settings.max_articles_per_run,
        publish_mode=settings.typefully_publish_mode,
        schedule_iso8601=settings.typefully_schedule_iso8601,
        enable_thread_generation=settings.enable_thread_generation,
        dry_run=settings.dry_run,
    )


def run() -> dict:
    setup_logging(settings.log_level)
    pipeline = build_pipeline()
    return pipeline.run_once()


def main() -> None:
    summary = run()
    print(json.dumps(summary, ensure_ascii=True))


# AWS Lambda handler

def lambda_handler(event, context):  # noqa: ANN001
    summary = run()
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
            },
            ensure_ascii=True,
        ),
    }


if __name__ == "__main__":
    main()
