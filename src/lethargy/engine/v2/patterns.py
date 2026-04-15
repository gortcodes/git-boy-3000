"""File-path and commit-message classifiers for engine v2.

Each predicate takes a list of repo file paths (or commit messages) and
returns a boolean or count. v0-pragmatic: path presence only, no content
parsing.
"""
import re
from collections.abc import Iterable

AI_TRAILER_PATTERN = re.compile(
    r"(?:Co-Authored-By:\s*(?:Claude|ChatGPT|Copilot|GPT)"
    r"|Generated with .{0,60}?Claude)",
    re.IGNORECASE,
)

AI_CONFIG_FILES = frozenset(
    {
        "CLAUDE.md",
        ".cursorrules",
        ".github/copilot-instructions.md",
    }
)


def has_helm(paths: Iterable[str]) -> bool:
    return any(
        p == "Chart.yaml"
        or p.endswith("/Chart.yaml")
        or p == "values.yaml"
        or p.endswith("/values.yaml")
        for p in paths
    )


def has_terraform(paths: Iterable[str]) -> bool:
    return any(p.endswith(".tf") or p.endswith(".tfvars") for p in paths)


def has_docker(paths: Iterable[str]) -> bool:
    return any(p == "Dockerfile" or p.endswith("/Dockerfile") for p in paths)


def has_github_actions(paths: Iterable[str]) -> bool:
    return any(
        p.startswith(".github/workflows/") and (p.endswith(".yml") or p.endswith(".yaml"))
        for p in paths
    )


def has_gitlab_ci(paths: Iterable[str]) -> bool:
    return any(p == ".gitlab-ci.yml" for p in paths)


def has_jenkins(paths: Iterable[str]) -> bool:
    return any(p == "Jenkinsfile" or p.endswith("/Jenkinsfile") for p in paths)


def has_prometheus(paths: Iterable[str]) -> bool:
    return any(
        p == "prometheus.yml"
        or p.endswith("/prometheus.yml")
        or p.startswith("prometheus/")
        for p in paths
    )


def has_grafana(paths: Iterable[str]) -> bool:
    return any(p.startswith("grafana/") or "/grafana/" in p for p in paths)


def has_otel(paths: Iterable[str]) -> bool:
    return any(
        ("otel" in p.lower() or "opentelemetry" in p.lower())
        and (p.endswith(".yml") or p.endswith(".yaml"))
        for p in paths
    )


def has_ai_config(paths: Iterable[str]) -> bool:
    return any(p in AI_CONFIG_FILES for p in paths)


def primary_language(languages: dict[str, int]) -> str | None:
    if not languages:
        return None
    return max(languages.items(), key=lambda item: item[1])[0]


def count_ai_trailers(events: list[dict]) -> int:
    count = 0
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        commits = (event.get("payload") or {}).get("commits") or []
        for commit in commits:
            message = commit.get("message", "")
            if AI_TRAILER_PATTERN.search(message):
                count += 1
    return count
