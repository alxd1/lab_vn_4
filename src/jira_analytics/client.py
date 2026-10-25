
"""Клиент для чтения данных Jira через REST API."""

import logging
import os
import time

import requests


LOG = logging.getLogger(__name__)


class JiraError(RuntimeError):
    """Исключение при ошибке получения данных из Jira."""


class JiraClient:
    """Клиент для получения задач Jira и истории изменения их статусов."""

    def __init__(self, base_url, api_version="2", timeout=25, page_size=100):
        """Инициализирует клиент Jira REST API."""
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api/{api_version}"

        self.timeout = timeout
        self.page_size = page_size

        # Создаём HTTP-сессию для повторного использования соединений.
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        # Настраиваем авторизацию, если заданы переменные окружения.
        if os.getenv("JIRA_USER") and os.getenv("JIRA_TOKEN"):
            self.session.auth = (
                os.environ["JIRA_USER"],
                os.environ["JIRA_TOKEN"]
            )

    def _get(self, path, params=None):
        """Выполняет GET-запрос с повторными попытками при ошибках."""
        url = f"{self.api_url}/{path.lstrip('/')}"

        # Допускаем не более трёх попыток выполнения запроса.
        for attempt in range(3):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )

                # Повторяем запрос при временных ошибках сервера.
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue

                response.raise_for_status()
                return response.json()

            except (requests.RequestException, ValueError) as exc:
                # Ошибки HTTP и исчерпание попыток завершают запрос.
                if isinstance(exc, requests.HTTPError) or attempt == 2:
                    raise JiraError(
                        f"Jira API request failed ({url}): {exc}"
                    ) from exc

                time.sleep(0.5 * (2 ** attempt))

        raise JiraError(f"Unable to fetch {url}")

    def search_issues(self, project, max_issues=None, jql=None):
        """Загружает задачи проекта с поддержкой JQL и пагинации."""
        issues = []
        start = 0

        while True:
            # Определяем количество задач для текущего запроса.
            limit = (
                self.page_size
                if max_issues is None
                else min(self.page_size, max_issues - len(issues))
            )

            if limit <= 0:
                break

            # Запрашиваем очередную страницу задач.
            payload = self._get(
                "search",
                {
                    "jql": jql or f'project = "{project}" ORDER BY created DESC',
                    "fields": "created,resolutiondate,status,assignee,reporter,priority,timespent",
                    "startAt": start,
                    "maxResults": limit
                }
            )

            page = payload.get("issues")

            # Проверяем структуру ответа Jira.
            if not isinstance(page, list):
                raise JiraError(
                    "Unexpected Jira search response: missing issues list"
                )

            issues.extend(page)
            start += len(page)

            LOG.info(
                "Loaded %s issues (project total: %s)",
                len(issues),
                payload.get("total", "?")
            )

            # Завершаем загрузку после получения последней страницы.
            if not page or start >= int(payload.get("total", start)):
                break

        return issues

    def status_history(self, key):
        """Получает полную историю переходов задачи между статусами."""
        changes = []
        start = 0
        legacy_fallback = False

        while True:
            if legacy_fallback:
                # Используем альтернативный API для старых версий Jira.
                payload = self._get(
                    f"issue/{key}",
                    {
                        "expand": "changelog",
                        "fields": "status"
                    }
                ).get("changelog", {})

                page = payload.get("histories")

            else:
                try:
                    # Получаем очередную страницу истории изменений.
                    payload = self._get(
                        f"issue/{key}/changelog",
                        {
                            "startAt": start,
                            "maxResults": self.page_size
                        }
                    )

                    page = payload.get("values")

                except JiraError as exc:
                    # При отсутствии endpoint переключаемся на старый API.
                    if start != 0 or "404" not in str(exc):
                        raise

                    LOG.info(
                        "Standalone changelog endpoint unsupported; "
                        "using expand=changelog"
                    )

                    legacy_fallback = True
                    continue

            # Проверяем корректность полученной истории.
            if not isinstance(page, list):
                raise JiraError(f"No changelog list for {key}")

            # Из всей истории изменений выбираем только переходы статусов.
            for history in page:
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        changes.append({
                            "at": history["created"],
                            "from": item.get("fromString"),
                            "to": item.get("toString")
                        })

            start += len(page)

            if legacy_fallback:
                # Старый API может возвращать неполную историю изменений.
                if start < int(payload.get("total", start)):
                    raise JiraError(
                        f"Truncated changelog for {key}: "
                        f"Jira expand=changelog returned "
                        f"{start}/{payload['total']} events; "
                        "cannot calculate exact status durations"
                    )

                break

            # Проверяем достижение последней страницы истории.
            if (
                not page
                or payload.get("isLast") is True
                or start >= int(payload.get("total", start))
            ):
                break

        return changes
