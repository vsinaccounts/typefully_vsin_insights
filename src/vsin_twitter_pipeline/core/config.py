from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="production", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    poll_interval_minutes: int = Field(default=15, alias="POLL_INTERVAL_MINUTES")
    max_articles_per_run: int = Field(default=10, alias="MAX_ARTICLES_PER_RUN")
    request_timeout_seconds: int = Field(default=20, alias="REQUEST_TIMEOUT_SECONDS")

    rss_feed_url: str = Field(alias="RSS_FEED_URL")
    user_agent: str = Field(default="vsin-twitter-pipeline/1.0", alias="USER_AGENT")

    database_url: str = Field(default="sqlite:///./pipeline.db", alias="DATABASE_URL")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.45, alias="OPENAI_TEMPERATURE")
    openai_max_output_tokens: int = Field(default=600, alias="OPENAI_MAX_OUTPUT_TOKENS")

    typefully_api_base: str = Field(default="https://api.typefully.com", alias="TYPEFULLY_API_BASE")
    typefully_api_key: str = Field(alias="TYPEFULLY_API_KEY")
    typefully_social_set_id: str = Field(alias="TYPEFULLY_SOCIAL_SET_ID")
    typefully_publish_mode: str = Field(default="draft", alias="TYPEFULLY_PUBLISH_MODE")
    typefully_schedule_iso8601: Optional[str] = Field(default=None, alias="TYPEFULLY_SCHEDULE_ISO8601")

    enable_thread_generation: bool = Field(default=True, alias="ENABLE_THREAD_GENERATION")
    dry_run: bool = Field(default=False, alias="DRY_RUN")


settings = Settings()
