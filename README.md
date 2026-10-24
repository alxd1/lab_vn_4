# Jira Task Analytics

Python CLI for the six reports required by the Jira analytics assignment. Default public project: **Apache Kafka**.

## Install and run (Linux, Python 3.10+)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
./run.sh
```

If the script is not executable after extracting an archive, run `bash run.sh`.
Open `reports/index.html` in a browser. Each plot is also saved as PNG.

Change `config.yaml` to select a different Jira Server/Data Center and project. Public Apache issues usually require no account. For authenticated instances set `JIRA_USER` and `JIRA_TOKEN` (never put secrets in YAML). API version 2 uses `/rest/api/2/search`; **Jira Cloud uses different search pagination and is not supported by this client**.

The default `max_issues: 300` limits network requests and generates a **sample-based** report, not project-wide statistics. Use `max_issues: null` for a full project export. This can take substantial time because status changelogs are fetched for every resolved issue.

## Verify and build

```bash
pytest -q
bash build.sh
```

Build creates a pip-installable wheel and `dist/jira-analytics-linux.tar.gz` containing a sample config and Linux launcher. On a target Linux machine install the wheel, then extract the launcher bundle and run it. The launcher expects `jira_analytics` to be installed in the active Python environment.

Alternatively extract the Linux bundle and run `bash install.sh` followed by `bash run.sh`; the installer creates a local virtual environment and installs the included wheel and its dependencies.

## Interpretation

1. Resolution age: hours between Jira `created` and `resolutiondate` for resolved issues.
2. Status durations: changelog-based hours between status transitions until resolution; one PNG per status.
3. Daily created and resolved counts plus cumulative totals, using UTC dates. For sampled projects, totals refer only to downloaded issues.
4. 30 users ranked by assignee + reporter occurrences; roles are counted separately (a task can count twice if a user fills both roles).
5. Jira `timespent` in hours for resolved issues, with `null` treated as 0; this is total recorded work on the issue, **not necessarily the assignee's work**.
6. Jira Priority as a **proxy** for severity, since Apache Jira projects generally have Priority but no universal Severity field.

*Resolved* means `resolutiondate` exists; it may include Won't Fix, Duplicate and other resolutions, not only Done/Closed. Reopened issues' lifetime is measured to their latest resolution date, while status transitions are reconstructed only within the creation-to-resolution window. Historical data can be inconsistent if the Jira instance has imported issues or incomplete change histories. Reports are read-only.

For older Jira instances (including Apache Jira), the client falls back to `expand=changelog` if the standalone changelog endpoint is unavailable. If Jira truncates that history, the application **stops with an explanatory error**, rather than silently plotting inaccurate status durations.
