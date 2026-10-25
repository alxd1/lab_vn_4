
"""Точка входа и управление выполнением аналитики Jira."""

import argparse
import logging
from pathlib import Path

import yaml

from .analysis import closed_issues, status_durations
from .charts import build_reports
from .client import JiraClient, JiraError


LOG = logging.getLogger(__name__)


def run(config_path):
    """Загружает задачи Jira и формирует аналитические отчёты."""

    # Загружаем конфигурацию приложения.
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))

    # Настраиваем уровень логирования и формат сообщений.
    logging.basicConfig(
        level=getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s"
    )

    jira = config["jira"]

    # Создаём клиент для взаимодействия с Jira REST API.
    client = JiraClient(
        jira["base_url"],
        jira.get("api_version", "2"),
        jira.get("timeout_seconds", 25),
        jira.get("page_size", 100)
    )

    # Загружаем основную выборку задач проекта.
    issues = client.search_issues(jira["project"], jira.get("max_issues"))

    # Получаем историю переходов для закрытых задач.
    histories = {}
    resolved = closed_issues(issues)

    for number, issue in enumerate(resolved, 1):
        LOG.info("Changelog %s/%s: %s", number, len(resolved), issue["key"])

        history = client.status_history(issue["key"])
        histories[issue["key"]] = status_durations(issue, history)

    # Отдельно выбираем закрытые задачи с зарегистрированным временем.
    worklog_jql = (
        f'project = "{jira["project"]}" '
        'AND resolution IS NOT EMPTY '
        'AND timeSpent > 0'
    )

    worklog_issues = client.search_issues(
        project=jira["project"],
        max_issues=None,
        jql=worklog_jql
    )

    LOG.info(
        "Found %s resolved issues with logged time",
        len(worklog_issues)
    )

    # Определяем каталог для сохранения отчётов.
    destination = Path(config.get("output_directory", "reports"))

    if not destination.is_absolute():
        destination = Path(config_path).resolve().parent / destination

    # Строим графики и формируем итоговую HTML-страницу.
    result = build_reports(
        issues,
        histories,
        destination,
        config.get("chart_bins", 25),
        jira["project"],
        worklog_issues=worklog_issues
    )

    print(f"Report generated: {result}")
    return result


def main():
    """Обрабатывает аргументы командной строки и ошибки выполнения."""

    parser = argparse.ArgumentParser(description="Jira REST API analytics")

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML settings"
    )

    args = parser.parse_args()

    # Перехватываем ожидаемые ошибки и выводим понятное сообщение.
    try:
        run(args.config)
    except (JiraError, OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
