#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m jira_analytics.cli --config config.yaml
else
  python3 -m jira_analytics.cli --config config.yaml
fi
