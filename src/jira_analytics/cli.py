"""Command-line entry point."""
import argparse
import logging
from pathlib import Path

import yaml

from .analysis import closed_issues, status_durations
from .charts import build_reports
from .client import JiraClient, JiraError

LOG = logging.getLogger(__name__)


def run(config_path):
    """Read configuration, retrieve Jira data and generate the chart collection."""
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s")
    jira = config["jira"]
    client = JiraClient(jira["base_url"], jira.get("api_version", "2"),
                        jira.get("timeout_seconds", 25), jira.get("page_size", 100))
    issues = client.search_issues(jira["project"], jira.get("max_issues"))
    histories = {}
    resolved = closed_issues(issues)
    for number, issue in enumerate(resolved, 1):
        LOG.info("Changelog %s/%s: %s", number, len(resolved), issue["key"])
        histories[issue["key"]] = status_durations(issue, client.status_history(issue["key"]))
    destination = Path(config.get("output_directory", "reports"))
    if not destination.is_absolute():
        destination = Path(config_path).resolve().parent / destination
    result = build_reports(issues, histories, destination, config.get("chart_bins", 25), jira["project"])
    print(f"Report generated: {result}")
    return result


def main():
    """Parse CLI arguments and turn anticipated failures into readable messages."""
    parser = argparse.ArgumentParser(description="Jira REST API analytics")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML settings")
    args = parser.parse_args()
    try:
        run(args.config)
    except (JiraError, OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
