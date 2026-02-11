# VSiN Content -> Twitter (Typefully) Pipeline

Production-ready Python scaffold for automatically turning new VSiN RSS articles into high-impact Twitter drafts in Typefully.

## 1) Architecture Overview

### Data flow
1. **RSS Ingestion Layer** polls `https://vsin.com/feed/`.
2. New entries are deduped using a deterministic `article_id` hash from `guid/id/link`.
3. **Article Extraction Layer** fetches full article HTML if RSS has only excerpt and extracts readable body text.
4. **Content Cleaning Layer** removes junk/disclaimers and normalizes text.
5. **Insight Extraction Layer** pulls likely betting-relevant stat/trend/odds lines.
6. **Tweet Generation Engine** (OpenAI) produces:
   - primary tweet
   - alternate tweet
   - hook tweet
   - optional 3-tweet thread
7. **Typefully Integration Layer** creates draft/scheduled/immediate post.
8. **Persistence + Observability Layer** records processed articles, drafts, run metrics, and failures.

### Runtime modes
- **Cron job**: `vsin-pipeline-run` every X minutes.
- **Worker**: long-running process called by scheduler.
- **Serverless**: `lambda_handler` (AWS) or Vercel function handler.

## 2) Step-by-Step Implementation Plan

1. Define environment and secrets (`.env`) for RSS, OpenAI, Typefully, DB.
2. Initialize DB schema (`processed_articles`, `pipeline_runs`, `tweet_drafts`).
3. Poll RSS and cap batch size per run (`MAX_ARTICLES_PER_RUN`).
4. Deduplicate by `article_id` and skip already-processed entries.
5. Extract article body from RSS content or full-page scrape.
6. Clean/normalize text and strip known disclaimer/legal lines.
7. Extract candidate stats/trends/angles used as prompt anchors.
8. Generate tweets via OpenAI with strict JSON response contract.
9. Validate constraints (280 char max, thread size=3 if present).
10. Send to Typefully (`draft`, `schedule`, or `publish_now`).
11. Persist draft metadata and mark article processed only after success.
12. Emit structured logs for each stage + retry transient failures.

## 3) Project Structure

```text
src/vsin_twitter_pipeline/
  core/
    config.py
    logging.py
  models/
    db.py
    schemas.py
  clients/
    rss_client.py
    http_client.py
    openai_client.py
    typefully_client.py
  services/
    repository.py
    article_extractor.py
    content_cleaner.py
    pipeline.py
  orchestration/
    main.py
    vercel_entry.py
.env.example
pyproject.toml
README.md
deployments/
```

## 4) Install & Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# fill env vars
vsin-pipeline-run
```

For validation without publishing:

```bash
DRY_RUN=true vsin-pipeline-run
```

## 5) OpenAI Prompt Template (Used in Code)

### System prompt
- Betting-intel editor voice (sharp, analytical, authoritative)
- No fabricated stats
- No URLs
- JSON-only output keys: `delivery_mode`, `single_tweet`, `thread`
- 280-character constraints

### User prompt fields
- Article title, author, publish date
- Cleaned article text (truncated for token safety)
- Extracted key points (stats/angles/trends)
- Thread enable/disable directive
- Explicit objective: actionable betting angle over recap

See: `src/vsin_twitter_pipeline/clients/openai_client.py`.

## 6) Typefully Integration

Implemented in `src/vsin_twitter_pipeline/clients/typefully_client.py`.

- Endpoint: `POST /v2/social-sets/{social_set_id}/drafts`
- Auth header: `X-API-KEY: <TYPEFULLY_API_KEY>`
- Supports:
  - Single tweet draft/publish/schedule
  - Thread (`thread: [tweet1, tweet2, tweet3]`)

Modes:
- `draft`: create draft only
- `schedule`: requires `TYPEFULLY_SCHEDULE_ISO8601`
- `publish_now`: immediate publish (`share=true`)

## 7) Database Schema

### Logical tables
- `processed_articles`
  - unique `article_id`, `url`, `title`, timestamps
- `pipeline_runs`
  - run status, timing, counts for found/processed/failed
- `tweet_drafts`
  - generated payload, remote draft id, publish mode, status

### SQL (portable)

```sql
CREATE TABLE processed_articles (
  id INTEGER PRIMARY KEY,
  article_id VARCHAR(512) UNIQUE NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  published_at TIMESTAMP NULL,
  processed_at TIMESTAMP NOT NULL
);

CREATE TABLE pipeline_runs (
  id INTEGER PRIMARY KEY,
  run_id VARCHAR(128) NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP NULL,
  status VARCHAR(32) NOT NULL,
  articles_found INTEGER NOT NULL,
  articles_processed INTEGER NOT NULL,
  articles_failed INTEGER NOT NULL
);

CREATE TABLE tweet_drafts (
  id INTEGER PRIMARY KEY,
  article_id VARCHAR(512) NOT NULL,
  draft_remote_id VARCHAR(256) NULL,
  draft_type VARCHAR(32) NOT NULL,
  payload TEXT NOT NULL,
  publish_mode VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL
);
```

## 8) Example Structured Logs

```json
{"ts":"2026-02-11T17:20:14.931Z","level":"INFO","logger":"vsin_twitter_pipeline.services.pipeline","msg":"pipeline started","event":"pipeline_start","run_id":"run_20260211T172014Z_b9e112fe"}
{"ts":"2026-02-11T17:20:22.488Z","level":"INFO","logger":"vsin_twitter_pipeline.services.pipeline","msg":"article processed","event":"article_processed","article_id":"2b6f...","run_id":"run_20260211T172014Z_b9e112fe"}
{"ts":"2026-02-11T17:20:23.712Z","level":"ERROR","logger":"vsin_twitter_pipeline.services.pipeline","msg":"article processing failed","event":"article_failed","article_id":"a641...","run_id":"run_20260211T172014Z_b9e112fe","error":"OpenAI timeout"}
{"ts":"2026-02-11T17:20:24.011Z","level":"INFO","logger":"vsin_twitter_pipeline.services.pipeline","msg":"pipeline complete","event":"pipeline_complete","run_id":"run_20260211T172014Z_b9e112fe","status":"completed_with_errors"}
```

## 9) Deployment Targets

### Vercel
- Use scheduled function hitting `orchestration.vercel_entry.handler`.
- Add env vars in Vercel dashboard.
- If using SQLite, mount external DB instead (Postgres recommended).

Example `deployments/vercel.json`:

```json
{
  "functions": {
    "api/pipeline.py": {
      "runtime": "python3.11"
    }
  },
  "crons": [
    {
      "path": "/api/pipeline",
      "schedule": "*/15 * * * *"
    }
  ]
}
```

### Railway
- Deploy with Dockerfile or Nixpacks.
- Set start command: `vsin-pipeline-run` (for cron-like one-shot use with Railway cron).
- Prefer managed Postgres.

### AWS Lambda
- Handler: `vsin_twitter_pipeline.orchestration.main.lambda_handler`
- Trigger with EventBridge rule (`rate(15 minutes)`).
- Store secrets in AWS Secrets Manager / SSM and inject as env vars.

### DigitalOcean
- **App Platform worker** with cron trigger calling command `vsin-pipeline-run`
- or **Droplet cron**:

```bash
*/15 * * * * cd /opt/vsin-twitter-pipeline && /opt/venv/bin/vsin-pipeline-run >> /var/log/vsin-pipeline.log 2>&1
```

## 10) Scalability Considerations

1. Move from SQLite to Postgres for concurrent workers.
2. Add queue layer (SQS/Celery/RQ) for per-article fan-out.
3. Add Redis lock to avoid overlapping runs.
4. Add content fingerprinting to avoid republishing materially identical updates.
5. Store raw article snapshots in object storage for auditability.
6. Add Prometheus metrics and alerting thresholds (failure rate, latency, token cost).
7. Add A/B testing for prompt variants and tweet engagement feedback loop.
8. Add dead-letter queue for failed articles requiring manual review.

## 11) Environment Variables

See `.env.example` for full list.

Critical:
- `OPENAI_API_KEY`
- `TYPEFULLY_API_KEY`
- `TYPEFULLY_SOCIAL_SET_ID`
- `DATABASE_URL`

## 12) Notes for Production Hardening

- Add Alembic migrations before go-live.
- Add unit/integration tests with mocked OpenAI and Typefully responses.
- Add outbound request circuit breaker and global rate limiting.
- Add moderation/check layer for compliance guardrails before publish mode.
