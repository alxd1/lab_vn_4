"""Pure data transformations for issue metrics."""
from collections import Counter, defaultdict
from datetime import datetime, timezone


def parse_date(value):
    """Parse Jira ISO timestamps into timezone-aware UTC datetimes."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def closed_issues(issues):
    """Filter issues that have a recorded resolution date."""
    return [i for i in issues if parse_date(i.get("fields", {}).get("resolutiondate"))]


def lifetime_hours(issue):
    """Return non-negative time from creation to last resolution in hours."""
    fields = issue["fields"]
    opened, closed = parse_date(fields.get("created")), parse_date(fields.get("resolutiondate"))
    return max(0.0, (closed - opened).total_seconds() / 3600) if opened and closed else None


def status_durations(issue, history):
    """Reconstruct durations in each status up to resolution, including repeats."""
    start = parse_date(issue["fields"]["created"])
    end = parse_date(issue["fields"].get("resolutiondate"))
    if not start or not end or end < start:
        return {}
    changes = sorted(history, key=lambda change: parse_date(change["at"]))
    status = changes[0].get("from") if changes else issue["fields"].get("status", {}).get("name")
    if not status:
        status = "Unknown"
    cursor = start
    result = defaultdict(float)
    for change in changes:
        at = parse_date(change["at"])
        if at < start:
            status = change.get("to") or status
            continue
        if at > end:
            break
        result[status] += max(0.0, (at - cursor).total_seconds() / 3600)
        cursor = at
        status = change.get("to") or status
    result[status] += max(0.0, (end - cursor).total_seconds() / 3600)
    return dict(result)


def daily_counts(issues):
    """Count created/resolved issues per UTC calendar day and cumulative totals."""
    created, resolved = Counter(), Counter()
    for issue in issues:
        fields = issue["fields"]
        opened = parse_date(fields.get("created"))
        closed = parse_date(fields.get("resolutiondate"))
        if opened:
            created[opened.date()] += 1
        if closed:
            resolved[closed.date()] += 1
    days = sorted(created.keys() | resolved.keys())
    totals = []
    a = b = 0
    for day in days:
        a += created[day]
        b += resolved[day]
        totals.append((day, created[day], resolved[day], a, b))
    return totals


def user_counts(issues):
    """Aggregate separate assignee and reporter counts by stable user identity."""
    counts = defaultdict(lambda: [0, 0])
    labels = {}
    for issue in issues:
        for index, role in enumerate(("assignee", "reporter")):
            user = issue["fields"].get(role)
            if not user:
                continue
            uid = user.get("accountId") or user.get("key") or user.get("name") or user.get("displayName")
            if uid:
                counts[uid][index] += 1
                labels[uid] = user.get("displayName") or uid
    return [(labels[uid], *values) for uid, values in
            sorted(counts.items(), key=lambda item: sum(item[1]), reverse=True)[:30]]


def priority_counts(issues):
    """Count tasks by Jira priority (used as the severity proxy)."""
    return Counter((i["fields"].get("priority") or {}).get("name") or "Unspecified" for i in issues)
