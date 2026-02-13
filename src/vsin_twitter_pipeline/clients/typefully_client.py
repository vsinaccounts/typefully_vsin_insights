from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from dateutil import parser as date_parser

from vsin_twitter_pipeline.models.schemas import DraftResult


class TypefullyClient:
    def __init__(self, api_base: str, api_key: str, social_set_id: str, timeout_seconds: int = 20):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.social_set_id = social_set_id
        self.timeout_seconds = timeout_seconds

    @retry(
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def create_single(self, content: str, mode: str = "draft", schedule_at: Optional[str] = None) -> DraftResult:
        payload = self._build_payload(posts=[content], mode=mode, schedule_at=schedule_at)
        response = self._post(payload)
        body = response.json()
        return DraftResult(remote_id=str(body.get("id") or body.get("draft", {}).get("id") or ""), status="ok")

    @retry(
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def create_thread(self, tweets: list[str], mode: str = "draft", schedule_at: Optional[str] = None) -> DraftResult:
        payload = self._build_payload(posts=tweets, mode=mode, schedule_at=schedule_at)
        response = self._post(payload)
        body = response.json()
        return DraftResult(remote_id=str(body.get("id") or body.get("draft", {}).get("id") or ""), status="ok")

    @retry(
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def get_latest_scheduled_publish_at(self) -> Optional[datetime]:
        url = f"{self.api_base}/v2/social-sets/{self.social_set_id}/drafts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        bodies: list[dict] = []
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            current_url: Optional[str] = url
            page_count = 0
            while current_url and page_count < 10:
                response = client.get(current_url, headers=headers)
                response.raise_for_status()
                body = response.json()
                if isinstance(body, dict):
                    bodies.append(body)
                current_url = body.get("next") if isinstance(body, dict) else None
                page_count += 1

        now_utc = datetime.now(timezone.utc)
        latest: Optional[datetime] = None
        for body in bodies:
            for value in self._extract_possible_schedule_values(body):
                dt = self._parse_dt(value)
                if not dt:
                    continue
                if dt < now_utc:
                    continue
                if latest is None or dt > latest:
                    latest = dt
        return latest

    def _build_payload(self, posts: list[str], mode: str, schedule_at: Optional[str]) -> dict:
        if mode not in {"draft", "schedule", "publish_now"}:
            raise ValueError("Invalid typefully mode")

        payload: dict = {
            "platforms": {
                "x": {
                    "enabled": True,
                    "posts": [{"text": text} for text in posts],
                }
            }
        }
        if mode == "publish_now":
            payload["publish_at"] = "now"
        elif mode == "schedule":
            if not schedule_at:
                raise ValueError("schedule_at is required for schedule mode")
            datetime.fromisoformat(schedule_at.replace("Z", "+00:00"))
            payload["publish_at"] = schedule_at
        return payload

    def _post(self, payload: dict) -> httpx.Response:
        url = f"{self.api_base}/v2/social-sets/{self.social_set_id}/drafts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response

    def _extract_possible_schedule_values(self, obj):  # noqa: ANN001
        schedule_keys = {
            "publish_at",
            "publishAt",
            "scheduled_at",
            "scheduledAt",
            "scheduled_date",
            "scheduledDate",
            "schedule-date",
            "scheduleDate",
        }
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in schedule_keys and isinstance(value, str):
                    yield value
                yield from self._extract_possible_schedule_values(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._extract_possible_schedule_values(item)

    @staticmethod
    def _parse_dt(value: str) -> Optional[datetime]:
        try:
            dt = date_parser.isoparse(value)
        except Exception:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
