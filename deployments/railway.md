# Railway Deployment

## Setup
1. Create new Railway project from repo.
2. Provision Postgres plugin.
3. Set `DATABASE_URL` to Railway Postgres URL.
4. Add all env vars from `.env.example`.
5. Use service start command: `vsin-pipeline-run`.
6. Create Railway cron trigger with desired interval (e.g., 15 minutes).

## Recommended
- Keep `TYPEFULLY_PUBLISH_MODE=draft` initially.
- Enable publish mode after verification.
