#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/opt/vsin-twitter-pipeline"
if [ -d "${PWD}/.venv" ] && [ -f "${PWD}/.env" ]; then
  ROOT_DIR="${PWD}"
fi

cd "${ROOT_DIR}"
source .venv/bin/activate

# Runs one polling cycle; dedupe logic prevents reprocessing old entries.
vsin-pipeline-run
