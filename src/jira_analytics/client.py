"""Read-only Jira Data Center/Server REST API client."""
import logging
import os
import time

import requests

LOG = logging.getLogger(__name__)


class JiraError(RuntimeError):
    """Raised when Jira data cannot be retrieved safely."""


class JiraClient:
    """Fetch project issues and complete status histories with pagination."""

    def __init__(self, base_url, api_version="2", timeout=25, page_size=100):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api/{api_version}"
        self.timeout = timeout
        self.page_size = page_size
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if os.getenv("JIRA_USER") and os.getenv("JIRA_TOKEN"):
            self.session.auth = (os.environ["JIRA_USER"], os.environ["JIRA_TOKEN"])

    def _get(self, path, params=None):
        """GET JSON with bounded retries for transient server failures."""
        url = f"{self.api_url}/{path.lstrip('/')}"
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                if isinstance(exc, requests.HTTPError) or attempt == 2:
                    raise JiraError(f"Jira API request failed ({url}): {exc}") from exc
                time.sleep(0.5 * (2 ** attempt))
        raise JiraError(f"Unable to fetch {url}")

    def search_issues(self, project, max_issues=None):
        """Retrieve issues via offset pagination; reject truncated/invalid responses."""
        issues = []
        start = 0
        while True:
            limit = self.page_size if max_issues is None else min(self.page_size, max_issues - len(issues))
            if limit <= 0:
                break
            payload = self._get("search", {
                "jql": f'project = "{project}" ORDER BY created DESC',
                "fields": "created,resolutiondate,status,assignee,reporter,priority,timespent",
                "startAt": start, "maxResults": limit,
            })
            page = payload.get("issues")
            if not isinstance(page, list):
                raise JiraError("Unexpected Jira search response: missing issues list")
            issues.extend(page)
            start += len(page)
            LOG.info("Loaded %s issues (project total: %s)", len(issues), payload.get("total", "?"))
            if not page or start >= int(payload.get("total", start)):
                break
        return issues

    def status_history(self, key):
        """Fetch every changelog page and retain only status transitions."""
        changes = []
        start = 0
        legacy_fallback = False
        while True:
            if legacy_fallback:
                payload = self._get(f"issue/{key}", {"expand": "changelog", "fields": "status"}).get("changelog", {})
                page = payload.get("histories")
            else:
                try:
                    payload = self._get(f"issue/{key}/changelog", {"startAt": start, "maxResults": self.page_size})
                    page = payload.get("values")
                except JiraError as exc:
                    if start != 0 or "404" not in str(exc):
                        raise
                    LOG.info("Standalone changelog endpoint unsupported; using expand=changelog")
                    legacy_fallback = True
                    continue
            if not isinstance(page, list):
                raise JiraError(f"No changelog list for {key}")
            for history in page:
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        changes.append({"at": history["created"], "from": item.get("fromString"),
                                        "to": item.get("toString")})
            start += len(page)
            if legacy_fallback:
                if start < int(payload.get("total", start)):
                    raise JiraError(f"Truncated changelog for {key}: Jira expand=changelog returned "
                                    f"{start}/{payload['total']} events; cannot calculate exact status durations")
                break
            if not page or payload.get("isLast") is True or start >= int(payload.get("total", start)):
                break
        return changes
