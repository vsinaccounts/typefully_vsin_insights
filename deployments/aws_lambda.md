# AWS Lambda Deployment

## Handler
`vsin_twitter_pipeline.orchestration.main.lambda_handler`

## Steps
1. Build deployment package (or container image) with Python 3.11.
2. Set environment variables from `.env.example`.
3. Configure EventBridge schedule, e.g. every 15 minutes.
4. Attach IAM permissions for Secrets Manager/SSM if used.
5. Use RDS Postgres or Aurora instead of SQLite for production.

## EventBridge Rule Example
- Schedule expression: `rate(15 minutes)`
- Target: Lambda function
