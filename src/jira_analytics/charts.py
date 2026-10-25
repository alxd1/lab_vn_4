
"""Построение аналитических графиков Jira в PNG и HTML."""

from collections import defaultdict
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from .analysis import (
    closed_issues,
    daily_counts,
    lifetime_hours,
    priority_counts,
    user_counts,
)


def _save(fig, output, filename):
    """Сохраняет график в PNG и освобождает ресурсы Matplotlib."""
    fig.tight_layout()
    fig.savefig(output / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return filename


def _hist(data, title, output, filename, bins):
    """Строит гистограмму распределения времени выполнения задач."""
    fig, ax = plt.subplots(figsize=(10, 5))

    if data:
        ax.hist(
            data,
            bins=min(bins, max(1, len(set(data)))),
            color="#3569a8",
            edgecolor="white"
        )
    else:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")

    ax.set(
        title=title,
        xlabel="Time (hours)",
        ylabel="Number of issues"
    )

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
    """Формирует шесть видов аналитических отчётов и HTML-страницу."""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)

    closed = closed_issues(issues)
    groups = []

    # 1. Распределение времени от создания до закрытия задачи.
    lifetimes = [
        lifetime_hours(issue)
        for issue in closed
        if lifetime_hours(issue) is not None
    ]

    lifetime_chart = _hist(
        lifetimes,
        "Time from creation to resolution",
        output,
        "01_lifetime.png",
        bins
    )

    groups.append(("1. Time to resolution", [lifetime_chart]))

    # 2. Распределение времени пребывания в каждом статусе.
    by_status = defaultdict(list)

    for issue in closed:
        for status, hours in histories.get(issue["key"], {}).items():
            by_status[status].append(hours)

    status_charts = []

    for index, status in enumerate(sorted(by_status), 1):
        filename = f"02_status_{index:02d}.png"

        chart = _hist(
            by_status[status],
            f"Time in status: {status}",
            output,
            filename,
            bins
        )

        status_charts.append(chart)

    if not status_charts:
        status_charts.append(
            _hist([], "Time in statuses", output, "02_status_empty.png", bins)
        )

    groups.append(("2. Time by status", status_charts))

    # 3. Ежедневное и накопительное количество задач.
    rows = daily_counts(issues)
    fig, ax = plt.subplots(figsize=(11, 5))

    if rows:
        dates = [row[0] for row in rows]

        series = [
            (1, "Created daily"),
            (2, "Resolved daily"),
            (3, "Created cumulative"),
            (4, "Resolved cumulative")
        ]

        for index, name in series:
            ax.plot(
                dates,
                [row[index] for row in rows],
                label=name,
                linewidth=2 if index >= 3 else 1,
                alpha=0.9
            )

        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

    ax.set(
        title="Created and resolved issues (UTC)",
        xlabel="Calendar day",
        ylabel="Issue count"
    )

    ax.grid(alpha=0.25)

    daily_chart = _save(fig, output, "03_daily.png")
    groups.append(("3. Daily activity and cumulative totals", [daily_chart]))

    # 4. Топ-30 пользователей по количеству назначенных и созданных задач.
    users = user_counts(issues)
    fig, ax = plt.subplots(figsize=(11, max(5, 0.34 * len(users) + 2)))

    if users:
        names = [user[0] for user in reversed(users)]
        assigned = [user[1] for user in reversed(users)]
        reported = [user[2] for user in reversed(users)]

        ax.barh(names, assigned, label="Assignee")
        ax.barh(names, reported, left=assigned, label="Reporter")
        ax.legend()

    ax.set(
        title="Top 30 users by assigned + reported issues",
        xlabel="Number of issues",
        ylabel="User"
    )

    users_chart = _save(fig, output, "04_users.png")
    groups.append(("4. Top users", [users_chart]))

    # 5. Распределение зарегистрированных трудозатрат.
    worklog_population = (
        closed if worklog_issues is None else closed_issues(worklog_issues)
    )

    # Значения timespent представлены в секундах.
    logged_time = [
        issue["fields"]["timespent"] / 3600
        for issue in worklog_population
        if issue["fields"].get("timespent") is not None
    ]

    worklog_chart = _hist(
        logged_time,
        "Logged time on resolved issues",
        output,
        "05_worklog.png",
        bins
    )

    groups.append(("5. Logged time", [worklog_chart]))

    # 6. Распределение задач по приоритетам.
    priority = priority_counts(issues)
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.bar(priority.keys(), priority.values(), color="#3569a8")

    ax.set(
        title="Issues by priority (severity proxy)",
        xlabel="Jira priority",
        ylabel="Number of issues"
    )

    ax.tick_params(axis="x", rotation=30)

    priority_chart = _save(fig, output, "06_priority.png")
    groups.append(("6. Severity / priority", [priority_chart]))

    # Формируем сводную информацию об обработанных данных.
    missing_work = sum(
        issue["fields"].get("timespent") is None
        for issue in worklog_population
    )

    note = (
        f"Project: {project}. "
        f"Issues retrieved: {len(issues)}. "
        f"Resolved: {len(closed)}. "
        f"Resolved issues with no logged time: {missing_work}. "
        f"Logged time observations: {len(logged_time)}. "
        "Times use UTC; status durations require complete changelogs. "
        "Severity is approximated by Jira Priority. "
        "The logged-time plot excludes missing values; "
        "it cannot attribute work to individual people. "
        "If max_issues is set, results describe only the retrieved subset, "
        "not the full project."
    )

    # Создаём HTML-страницу со всеми графиками.
    html = [
        "<!doctype html>",
        "<html lang='en'>",
        "<meta charset='utf-8'>",
        "<title>Jira Analytics</title>",
        (
            "<style>"
            "body{font:16px system-ui;max-width:1100px;margin:auto;"
            "padding:2rem;color:#223}"
            "img{max-width:100%;border:1px solid #ddd;margin:0.5rem 0 2rem}"
            "p{line-height:1.6}"
            "</style>"
        ),
        f"<h1>Jira Analytics: {escape(project)}</h1>",
        f"<p>{escape(note)}</p>"
    ]

    for title, images in groups:
        html.append(f"<h2>{escape(title)}</h2>")

        for filename in images:
            html.append(
                f"<img src='{escape(filename)}' alt='{escape(title)}'>"
            )

    html.append("</html>")

    # Сохраняем HTML-отчёт.
    report_path = output / "index.html"
    report_path.write_text("\n".join(html), encoding="utf-8")

    return report_path
