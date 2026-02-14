import json

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vsin_twitter_pipeline.models.schemas import Article, TweetPackage


SYSTEM_PROMPT = """
You are VSiN's betting intelligence social editor.

Voice requirements:
- Sharp, analytical, authoritative, no hype.
- Prioritize edge, market inefficiency, trend durability, and betting utility.
- Avoid emojis unless context demands one (rare).
- Never fabricate data, odds, injuries, or trends.
- Do not include URLs.

Output requirements:
- Return valid JSON only with keys: delivery_mode, single_tweet, thread
- delivery_mode must be exactly "single" or "thread".
- If delivery_mode is "single": single_tweet must be <= 280 chars and thread must be [].
- If delivery_mode is "thread": thread must be an array of exactly 3 tweets, each <= 280 chars, and single_tweet must be "".
- For thread mode, tweet 1 must be a compelling hook that creates curiosity and frames the betting angle immediately.
- Tweets must be standalone and insight-first, not article recaps.
""".strip()

FACT_CHECK_PROMPT = """
You are a strict factual verifier for VSiN social copy.

Rules:
- Do not introduce any new names, stats, records, locations, or qualifiers not supported by the source.
- If a claim is ambiguous or unsupported, remove it.
- Preserve clarity and impact, but prefer omission over invention.
- Return valid JSON only with keys: delivery_mode, single_tweet, thread.
- Keep all character limits intact (<=280 per tweet).
""".strip()


class OpenAIClient:
    def __init__(self, api_key: str, model: str, temperature: float, max_output_tokens: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    @retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def generate_tweets(self, article: Article, enable_thread_generation: bool) -> TweetPackage:
        prompt = self._build_user_prompt(article, enable_thread_generation)

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)

        tweet_package = TweetPackage(
            delivery_mode=str(payload.get("delivery_mode", "")).strip().lower(),
            single_tweet=str(payload.get("single_tweet", "")).strip(),
            thread=[str(x).strip() for x in payload.get("thread", []) if str(x).strip()],
        )
        self._validate(tweet_package, enable_thread_generation)
        verified = self._fact_check_and_rewrite(article, tweet_package, enable_thread_generation)
        self._validate(verified, enable_thread_generation)
        return verified

    def _build_user_prompt(self, article: Article, enable_thread_generation: bool) -> str:
        key_points = "\n".join(f"- {point}" for point in article.extracted_insights[:12])
        return f"""
ARTICLE TITLE: {article.title}
AUTHOR: {article.author or "Unknown"}
PUBLISHED: {article.published_at.isoformat() if article.published_at else "Unknown"}

ARTICLE TEXT (authoritative source):
{article.clean_text[:14000]}

EXTRACTED DATA POINTS:
{key_points if key_points else "- none extracted"}

Generation goals:
- Default to ONE singular tweet.
- Treat thread output as rare and only use it when absolutely necessary for clarity.
- Do NOT summarize the full article slate.
- Do NOT cover multiple games just because the article includes them.
- Do NOT bundle multiple betting angles in one post.
- Pick the single strongest, most actionable betting edge and write around that one idea.
- Keep scope narrow: one game OR one matchup OR one betting angle.
- Emphasize actionable framing: market mispricing, trend context, or risk-adjusted takeaway.
- If data is weak, use restraint and be explicit about uncertainty.
- Choose exactly one output path: single tweet OR 3-tweet thread (never both).
- Thread allowed: {str(enable_thread_generation).lower()} (only return thread mode when article has sufficient depth).
- Only choose thread mode when the article has enough depth for 3 distinct, non-redundant betting insights.
- If thread mode is chosen, tweet 1 must be a hard hook, tweet 2 expands evidence, tweet 3 lands the actionable betting takeaway.
""".strip()

    @staticmethod
    def _validate(tweet_package: TweetPackage, enable_thread_generation: bool) -> None:
        if tweet_package.delivery_mode not in {"single", "thread"}:
            raise ValueError("delivery_mode must be either 'single' or 'thread'")

        if tweet_package.delivery_mode == "single":
            if not tweet_package.single_tweet:
                raise ValueError("Missing single_tweet in single mode")
            if len(tweet_package.single_tweet) > 280:
                raise ValueError("single_tweet exceeds 280 characters")
            if tweet_package.thread:
                raise ValueError("thread must be empty in single mode")
            return

        if not enable_thread_generation:
            raise ValueError("Thread returned while thread generation is disabled")
        if tweet_package.single_tweet:
            raise ValueError("single_tweet must be empty in thread mode")
        if len(tweet_package.thread) != 3:
            raise ValueError("Thread must have exactly 3 tweets")
        for idx, tweet in enumerate(tweet_package.thread, start=1):
            if len(tweet) > 280:
                raise ValueError(f"thread tweet {idx} exceeds 280 characters")

    def _fact_check_and_rewrite(
        self, article: Article, draft: TweetPackage, enable_thread_generation: bool
    ) -> TweetPackage:
        draft_json = {
            "delivery_mode": draft.delivery_mode,
            "single_tweet": draft.single_tweet,
            "thread": draft.thread,
        }
        key_points = "\n".join(f"- {point}" for point in article.extracted_insights[:20])
        prompt = f"""
SOURCE ARTICLE TEXT:
{article.clean_text[:14000]}

SOURCE DATA POINTS:
{key_points if key_points else "- none extracted"}

DRAFT OUTPUT JSON:
{json.dumps(draft_json, ensure_ascii=True)}

Task:
- Verify every claim against SOURCE ARTICLE TEXT.
- Correct any factual drift, attribution drift, or scope drift.
- Keep tone sharp and concise while staying source-grounded.
- Keep same JSON schema.
- Thread allowed: {str(enable_thread_generation).lower()}.
""".strip()

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=self.max_output_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FACT_CHECK_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return TweetPackage(
            delivery_mode=str(payload.get("delivery_mode", "")).strip().lower(),
            single_tweet=str(payload.get("single_tweet", "")).strip(),
            thread=[str(x).strip() for x in payload.get("thread", []) if str(x).strip()],
        )
