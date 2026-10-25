
"""Функции аналитической обработки задач Jira."""

from collections import Counter, defaultdict
from datetime import datetime, timezone


def parse_date(value):
    """Преобразует дату Jira в datetime с часовым поясом UTC."""
    if not value:
        return None

    normalized_value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized_value).astimezone(timezone.utc)


def closed_issues(issues):
    """Возвращает список задач с заполненной датой завершения."""
    return [
        issue
        for issue in issues
        if parse_date(issue.get("fields", {}).get("resolutiondate"))
    ]


def lifetime_hours(issue):
    """Вычисляет время от создания до завершения задачи в часах."""
    fields = issue["fields"]

    opened = parse_date(fields.get("created"))
    closed = parse_date(fields.get("resolutiondate"))

    if not opened or not closed:
        return None

    duration_hours = (closed - opened).total_seconds() / 3600
    return max(0.0, duration_hours)


def status_durations(issue, history):
    """Рассчитывает суммарное время пребывания задачи в каждом статусе."""
    start = parse_date(issue["fields"]["created"])
    end = parse_date(issue["fields"].get("resolutiondate"))

    if not start or not end or end < start:
        return {}

    # Упорядочиваем переходы между статусами по времени.
    changes = sorted(history, key=lambda change: parse_date(change["at"]))

    # Определяем первоначальный статус задачи.
    if changes:
        status = changes[0].get("from")
    else:
        status = issue["fields"].get("status", {}).get("name")

    if not status:
        status = "Unknown"

    cursor = start
    result = defaultdict(float)

    for change in changes:
        at = parse_date(change["at"])

        # Переходы до создания задачи не учитываются.
        if at < start:
            status = change.get("to") or status
            continue

        # Переходы после закрытия задачи не учитываются.
        if at > end:
            break

        # При повторном посещении статуса время суммируется.
        duration_hours = max(0.0, (at - cursor).total_seconds() / 3600)
        result[status] += duration_hours

        cursor = at
        status = change.get("to") or status

    # Учитываем интервал от последнего перехода до закрытия.
    final_duration = max(0.0, (end - cursor).total_seconds() / 3600)
    result[status] += final_duration

    return dict(result)


def daily_counts(issues):
    """Подсчитывает ежедневное и накопительное количество задач."""
    created = Counter()
    resolved = Counter()

    for issue in issues:
        fields = issue["fields"]

        opened = parse_date(fields.get("created"))
        closed = parse_date(fields.get("resolutiondate"))

        if opened:
            created[opened.date()] += 1

        if closed:
            resolved[closed.date()] += 1

    # Формируем упорядоченный набор дат с активностью.
    days = sorted(created.keys() | resolved.keys())

    totals = []
    created_cumulative = 0
    resolved_cumulative = 0

    for day in days:
        created_cumulative += created[day]
        resolved_cumulative += resolved[day]

        totals.append((
            day,
            created[day],
            resolved[day],
            created_cumulative,
            resolved_cumulative
        ))

    return totals


def user_counts(issues):
    """Возвращает топ-30 пользователей по количеству задач в двух ролях."""
    counts = defaultdict(lambda: [0, 0])
    labels = {}

    for issue in issues:
        for index, role in enumerate(("assignee", "reporter")):
            user = issue["fields"].get(role)

            if not user:
                continue

            # Используем наиболее устойчивый доступный идентификатор.
            uid = (
                user.get("accountId")
                or user.get("key")
                or user.get("name")
                or user.get("displayName")
            )

            if not uid:
                continue

            # Индекс 0 — исполнитель, индекс 1 — репортёр.
            counts[uid][index] += 1
            labels[uid] = user.get("displayName") or uid

    # Сортируем по суммарному количеству задач в обеих ролях.
    sorted_users = sorted(
        counts.items(),
        key=lambda item: sum(item[1]),
        reverse=True
    )

    return [
        (labels[uid], assigned_count, reported_count)
        for uid, (assigned_count, reported_count) in sorted_users[:30]
    ]


def priority_counts(issues):
    """Подсчитывает количество задач по приоритетам Jira."""
    return Counter(
        (issue["fields"].get("priority") or {}).get("name") or "Unspecified"
        for issue in issues
    )
