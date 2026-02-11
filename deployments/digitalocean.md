# DigitalOcean Deployment

## App Platform (recommended)
1. Deploy as worker component using Dockerfile.
2. Set env vars and managed Postgres.
3. Configure periodic run via App Platform Job cron schedule: `*/30 * * * *`.
4. Command: `bash /workspace/scripts/run_pipeline.sh`

## Droplet + Cron
1. Provision a Droplet and install Python 3.9+.
2. Clone repo to `/opt/vsin-twitter-pipeline`.
3. Create virtualenv and install:

```bash
cd /opt/vsin-twitter-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

4. Add your production `.env` file at `/opt/vsin-twitter-pipeline/.env`.
5. Ensure log path exists:

```bash
sudo mkdir -p /var/log
sudo touch /var/log/vsin-pipeline.log
```

6. Add cron entry (every 30 minutes, no overlapping runs):

```bash
*/30 * * * * cd /opt/vsin-twitter-pipeline && /usr/bin/flock -n /tmp/vsin-pipeline.lock /bin/bash /opt/vsin-twitter-pipeline/scripts/run_pipeline.sh >> /var/log/vsin-pipeline.log 2>&1
```
