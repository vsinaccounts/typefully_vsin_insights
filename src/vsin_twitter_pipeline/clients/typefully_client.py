from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vsin_twitter_pipeline.models.schemas import DraftResult
from typing import Optional


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
