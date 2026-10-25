"""Matplotlib report rendering (PNG and HTML index)."""
from collections import defaultdict
from html import escape
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .analysis import closed_issues, daily_counts, lifetime_hours, priority_counts, user_counts


def _save(fig, output, filename):
    fig.tight_layout()
    fig.savefig(output / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return filename


def _hist(data, title, output, filename, bins):
    fig, ax = plt.subplots(figsize=(10, 5))
    if data:
        ax.hist(data, bins=min(bins, max(1, len(set(data)))), color="#3569a8", edgecolor="white")
    else:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
    ax.set(title=title, xlabel="Time (hours)", ylabel="Number of issues")
    ax.grid(axis="y", alpha=0.25)
    return _save(fig, output, filename)


def build_reports(
    issues,
    histories,
    directory,
    bins=25,
    project="JIRA",
    worklog_issues=None
):
    """Render six report families and an HTML index; status family has one plot per status."""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    closed = closed_issues(issues)
    groups = []

    groups.append(("1. Time to resolution", [_hist(
        [lifetime_hours(i) for i in closed if lifetime_hours(i) is not None],
        "Time from creation to resolution", output, "01_lifetime.png", bins)]))

    by_status = defaultdict(list)
    for issue in closed:
        for status, hours in histories.get(issue["key"], {}).items():
            by_status[status].append(hours)
    files = []
    for index, status in enumerate(sorted(by_status), 1):
        files.append(_hist(by_status[status], f"Time in status: {status}", output,
                           f"02_status_{index:02d}.png", bins))
    if not files:
        files.append(_hist([], "Time in statuses", output, "02_status_empty.png", bins))
    groups.append(("2. Time by status", files))

    rows = daily_counts(issues)
    fig, ax = plt.subplots(figsize=(11, 5))
    if rows:
        dates = [r[0] for r in rows]
        for pos, name in [(1, "Created daily"), (2, "Resolved daily"),
                          (3, "Created cumulative"), (4, "Resolved cumulative")]:
            ax.plot(dates, [r[pos] for r in rows], label=name,
                    linewidth=2 if pos >= 3 else 1, alpha=0.9)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
    ax.set(title="Created and resolved issues (UTC)", xlabel="Calendar day", ylabel="Issue count")
    ax.grid(alpha=0.25)
    groups.append(("3. Daily activity and cumulative totals", [_save(fig, output, "03_daily.png")]))

    users = user_counts(issues)
    fig, ax = plt.subplots(figsize=(11, max(5, 0.34 * len(users) + 2)))
    if users:
        names = [x[0] for x in reversed(users)]
        assigned = [x[1] for x in reversed(users)]
        reported = [x[2] for x in reversed(users)]
        ax.barh(names, assigned, label="Assignee")
        ax.barh(names, reported, left=assigned, label="Reporter")
        ax.legend()
    ax.set(title="Top 30 users by assigned + reported issues", xlabel="Number of issues", ylabel="User")
    groups.append(("4. Top users", [_save(fig, output, "04_users.png")]))

    worklog_population = (
        closed
        if worklog_issues is None
        else closed_issues(worklog_issues)
    )

    logged_time = [
        issue["fields"]["timespent"] / 3600
        for issue in worklog_population
        if issue["fields"].get("timespent") is not None
    ]

    groups.append(("5. Logged time", [_hist(
        logged_time,
        "Logged time on resolved issues",
        output,
        "05_worklog.png",
        bins
    )]))

    priority = priority_counts(issues)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(priority.keys(), priority.values(), color="#3569a8")
    ax.set(title="Issues by priority (severity proxy)", xlabel="Jira priority", ylabel="Number of issues")
    ax.tick_params(axis="x", rotation=30)
    groups.append(("6. Severity / priority", [_save(fig, output, "06_priority.png")]))

    missing_work = sum(
        i["fields"].get("timespent") is None
        for i in worklog_population
    )
    note = (f"Project: {project}. Issues retrieved: {len(issues)}. Resolved: {len(closed)}. "
            f"Resolved issues with no logged time: {missing_work}. "
            f"Logged time observations: {len(logged_time)}. "
            "Times use UTC; status durations require complete changelogs. "
            "Severity is approximated by Jira Priority. "
            "The logged-time plot excludes missing values; it cannot attribute work to individual people. "
            "If max_issues is set, results describe only the retrieved subset, not the full project.")
    html = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
            "<title>Jira Analytics</title><style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:2rem;color:#223}img{max-width:100%;border:1px solid #ddd;margin:0.5rem 0 2rem}p{line-height:1.6}</style>",
            f"<h1>Jira Analytics: {escape(project)}</h1><p>{escape(note)}</p>"]
    for title, images in groups:
        html.append(f"<h2>{escape(title)}</h2>")
        html.extend(f"<img src='{escape(name)}' alt='{escape(title)}'>" for name in images)
    html.append("</html>")
    (output / "index.html").write_text("\n".join(html), encoding="utf-8")
    return output / "index.html"
