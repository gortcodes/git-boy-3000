from collections import Counter

from lethargy.engine.domain import RawSnapshot, SignalsV2
from lethargy.engine.v1 import extract as v1_extract
from lethargy.engine.v2 import patterns

ENGINE_VERSION = 2


def extract(snapshot: RawSnapshot) -> SignalsV2:
    v1 = v1_extract.extract(snapshot)

    infra = _count_infra(snapshot.repo_trees)
    cicd = _count_cicd(snapshot.repo_trees)
    obs = _count_observability(snapshot.repo_trees)
    lang = _count_primary_languages(snapshot.repo_languages)
    ai_configs = sum(
        1 for paths in snapshot.repo_trees.values() if patterns.has_ai_config(paths)
    )
    ai_trailers = patterns.count_ai_trailers(snapshot.events)
    weekly_active = sum(1 for w in v1.weekly_commits if w > 0)

    return SignalsV2(
        engine_version=ENGINE_VERSION,
        helm_count=infra["helm"],
        terraform_count=infra["terraform"],
        docker_count=infra["docker"],
        github_actions_count=cicd["github_actions"],
        gitlab_ci_count=cicd["gitlab_ci"],
        jenkins_count=cicd["jenkins"],
        longest_streak_days=v1.longest_streak_days,
        total_commit_contributions=v1.total_commit_contributions,
        total_pr_contributions=v1.total_pr_contributions,
        python_primary_count=lang["python"],
        javascript_primary_count=lang["javascript"],
        typescript_primary_count=lang["typescript"],
        prometheus_count=obs["prometheus"],
        grafana_count=obs["grafana"],
        otel_count=obs["otel"],
        total_pr_review_contributions=v1.total_pr_review_contributions,
        issue_comment_event_count=v1.issue_comment_event_count,
        distinct_external_repos_touched=v1.distinct_external_repos_touched,
        ai_trailers_count=ai_trailers,
        ai_configs_count=ai_configs,
        account_age_days=v1.account_age_days,
        activity_span_days=v1.activity_span_days,
        current_streak_days=v1.current_streak_days,
        weekly_active_weeks=weekly_active,
        hour_histogram=list(v1.hour_histogram),
    )


def _count_infra(repo_trees: dict[str, list[str]]) -> dict[str, int]:
    return {
        "helm": sum(1 for paths in repo_trees.values() if patterns.has_helm(paths)),
        "terraform": sum(
            1 for paths in repo_trees.values() if patterns.has_terraform(paths)
        ),
        "docker": sum(1 for paths in repo_trees.values() if patterns.has_docker(paths)),
    }


def _count_cicd(repo_trees: dict[str, list[str]]) -> dict[str, int]:
    return {
        "github_actions": sum(
            1 for paths in repo_trees.values() if patterns.has_github_actions(paths)
        ),
        "gitlab_ci": sum(
            1 for paths in repo_trees.values() if patterns.has_gitlab_ci(paths)
        ),
        "jenkins": sum(
            1 for paths in repo_trees.values() if patterns.has_jenkins(paths)
        ),
    }


def _count_observability(repo_trees: dict[str, list[str]]) -> dict[str, int]:
    return {
        "prometheus": sum(
            1 for paths in repo_trees.values() if patterns.has_prometheus(paths)
        ),
        "grafana": sum(
            1 for paths in repo_trees.values() if patterns.has_grafana(paths)
        ),
        "otel": sum(1 for paths in repo_trees.values() if patterns.has_otel(paths)),
    }


def _count_primary_languages(
    repo_languages: dict[str, dict[str, int]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for langs in repo_languages.values():
        primary = patterns.primary_language(langs)
        if primary:
            counts[primary] += 1
    return {
        "python": counts.get("Python", 0),
        "javascript": counts.get("JavaScript", 0),
        "typescript": counts.get("TypeScript", 0),
    }
