from jira_analytics.analysis import (closed_issues, daily_counts, lifetime_hours,
                                     priority_counts, status_durations, user_counts)


def issue(key="KAFKA-1", closed="2026-01-02T00:00:00Z"):
    return {"key": key, "fields": {"created": "2026-01-01T00:00:00Z",
            "resolutiondate": closed, "status": {"name": "Done"}, "priority": {"name": "Major"},
            "assignee": {"key": "a", "displayName": "Alice"},
            "reporter": {"key": "b", "displayName": "Bob"}, "timespent": 3600}}


def test_closed_only():
    assert len(closed_issues([issue(), issue("KAFKA-2", None)])) == 1


def test_lifetime():
    assert lifetime_hours(issue()) == 24


def test_status_durations_repeated_status():
    changes = [{"at": "2026-01-01T06:00:00Z", "from": "Open", "to": "Review"},
               {"at": "2026-01-01T12:00:00Z", "from": "Review", "to": "Open"}]
    assert status_durations(issue(), changes) == {"Open": 18, "Review": 6}


def test_daily_counts():
    assert daily_counts([issue()]) == [(issue_date(1), 1, 0, 1, 0),
                                      (issue_date(2), 0, 1, 1, 1)]


def issue_date(day):
    from datetime import date
    return date(2026, 1, day)


def test_user_roles():
    assert user_counts([issue()]) == [("Alice", 1, 0), ("Bob", 0, 1)]


def test_priority_counts():
    assert priority_counts([issue(), issue("KAFKA-2")]) == {"Major": 2}
