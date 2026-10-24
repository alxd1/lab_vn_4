from jira_analytics.client import JiraClient


def test_search_pagination(monkeypatch):
    client = JiraClient("https://example.test", page_size=1)
    requested = []

    def fake_get(path, params):
        requested.append(params["startAt"])
        return {"issues": [{"key": f"TEST-{params['startAt'] + 1}"}], "total": 2}

    monkeypatch.setattr(client, "_get", fake_get)
    assert len(client.search_issues("TEST")) == 2
    assert requested == [0, 1]


def test_changelog_pagination(monkeypatch):
    client = JiraClient("https://example.test", page_size=1)

    def fake_get(path, params):
        at = params["startAt"]
        return {"values": [{"created": "2026-01-01T00:00:00Z", "items": [
            {"field": "status", "fromString": "A", "toString": "B"}]}],
            "total": 2, "isLast": at == 1}

    monkeypatch.setattr(client, "_get", fake_get)
    assert len(client.status_history("TEST-1")) == 2


def test_legacy_changelog_fallback(monkeypatch):
    from jira_analytics.client import JiraError
    client = JiraClient("https://example.test")

    def fake_get(path, params):
        if path.endswith("/changelog"):
            raise JiraError("404 Not Found")
        return {"changelog": {"histories": [{"created": "2026-01-01T00:00:00Z",
                 "items": [{"field": "status", "fromString": "Open", "toString": "Done"}]}],
                 "total": 1}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert client.status_history("TEST-1")[0]["to"] == "Done"
