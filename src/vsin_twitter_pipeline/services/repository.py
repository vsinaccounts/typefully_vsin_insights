import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from vsin_twitter_pipeline.models.db import Database, PipelineRun, ProcessedArticle, TweetDraft


class Repository:
    def __init__(self, db: Database):
        self.db = db

    def is_processed(self, article_id: str) -> bool:
        with self.db.SessionLocal() as session:
            stmt = select(ProcessedArticle.id).where(ProcessedArticle.article_id == article_id)
            return session.execute(stmt).scalar_one_or_none() is not None

    def mark_processed(
        self,
        article_id: str,
        url: str,
        title: str,
        published_at: Optional[datetime],
    ) -> None:
        with self.db.SessionLocal() as session:
            session.add(
                ProcessedArticle(
                    article_id=article_id,
                    url=url,
                    title=title,
                    published_at=published_at,
                    processed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    def get_last_draft_created_at(self) -> Optional[datetime]:
        with self.db.SessionLocal() as session:
            stmt = select(func.max(TweetDraft.created_at))
            value = session.execute(stmt).scalar_one_or_none()
            return value

    def create_run(self, run_id: str) -> int:
        with self.db.SessionLocal() as session:
            run = PipelineRun(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                completed_at=None,
                status="running",
                articles_found=0,
                articles_processed=0,
                articles_failed=0,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id

    def finalize_run(
        self,
        run_row_id: int,
        status: str,
        articles_found: int,
        articles_processed: int,
        articles_failed: int,
    ) -> None:
        with self.db.SessionLocal() as session:
            run = session.get(PipelineRun, run_row_id)
            if not run:
                return
            run.completed_at = datetime.now(timezone.utc)
            run.status = status
            run.articles_found = articles_found
            run.articles_processed = articles_processed
            run.articles_failed = articles_failed
            session.commit()

    def record_draft(
        self,
        article_id: str,
        draft_type: str,
        payload: dict,
        publish_mode: str,
        status: str,
        remote_id: Optional[str] = None,
    ) -> None:
        with self.db.SessionLocal() as session:
            session.add(
                TweetDraft(
                    article_id=article_id,
                    draft_remote_id=remote_id,
                    draft_type=draft_type,
                    payload=json.dumps(payload, ensure_ascii=True),
                    publish_mode=publish_mode,
                    status=status,
                )
            )
            session.commit()
