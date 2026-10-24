#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install --upgrade build
python3 -m build
mkdir -p dist/jira-analytics-linux
cp config.yaml run.sh install.sh dist/*.whl dist/jira-analytics-linux/
chmod +x dist/jira-analytics-linux/run.sh dist/jira-analytics-linux/install.sh
tar -czf dist/jira-analytics-linux.tar.gz -C dist jira-analytics-linux
echo "Produced wheel and Linux bundle in dist/"
