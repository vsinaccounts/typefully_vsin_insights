CREATE TABLE IF NOT EXISTS processed_articles (
  id INTEGER PRIMARY KEY,
  article_id VARCHAR(512) UNIQUE NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  published_at TIMESTAMP NULL,
  processed_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id INTEGER PRIMARY KEY,
  run_id VARCHAR(128) NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP NULL,
  status VARCHAR(32) NOT NULL,
  articles_found INTEGER NOT NULL,
  articles_processed INTEGER NOT NULL,
  articles_failed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tweet_drafts (
  id INTEGER PRIMARY KEY,
  article_id VARCHAR(512) NOT NULL,
  draft_remote_id VARCHAR(256) NULL,
  draft_type VARCHAR(32) NOT NULL,
  payload TEXT NOT NULL,
  publish_mode VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL
);
