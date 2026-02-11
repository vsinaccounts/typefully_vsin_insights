import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class HTTPClient:
    def __init__(self, timeout_seconds: int, user_agent: str):
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    @retry(
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def get_text(self, url: str) -> str:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
            return response.text
