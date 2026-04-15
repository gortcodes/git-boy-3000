import math
from datetime import datetime

from lethargy.engine.domain import CharacterSheetV2, SignalsV2, StatV2, SubStatV2

ENGINE_VERSION = 2


def score(
    signals: SignalsV2,
    *,
    username: str,
    class_name: str,
    fetched_at: datetime,
    computed_at: datetime,
    raw_schema_version: int,
) -> CharacterSheetV2:
    stats = {
        "STR": _score_str(signals),
        "AGI": _score_agi(signals),
        "END": _score_end(signals),
        "INT": _score_int(signals),
        "PER": _score_per(signals),
        "CHA": _score_cha(signals),
        "LUCK": _score_luck(signals),
    }
    character_level = sum(stat.level for stat in stats.values())
    flavor = {
        "account_age_days": signals.account_age_days,
        "activity_span_days": signals.activity_span_days,
        "current_streak_days": signals.current_streak_days,
        "longest_streak_days": signals.longest_streak_days,
        "weekly_active_weeks": signals.weekly_active_weeks,
        "hour_histogram": list(signals.hour_histogram),
    }
    return CharacterSheetV2(
        username=username,
        engine_version=ENGINE_VERSION,
        raw_schema_version=raw_schema_version,
        fetched_at=fetched_at,
        computed_at=computed_at,
        class_name=class_name,
        character_level=character_level,
        stats=stats,
        flavor=flavor,
    )


def _log2_level(raw: int, weight: float) -> int:
    if raw <= 0:
        return 0
    return max(0, round(math.log2(raw + 1) * weight))


def _make_stat(name: str, display: str, sub_stats: list[tuple[str, int]]) -> StatV2:
    sub_list = [SubStatV2(name=n, level=lvl) for n, lvl in sub_stats]
    # Every parent stat starts at a base of 1; sub-stats add on top.
    # An empty stat reads as 1. A stat with one 1-point sub-stat reads as 2.
    level = 1 + sum(s.level for s in sub_list)
    return StatV2(name=name, display=display, level=level, sub_stats=sub_list)


def _score_str(s: SignalsV2) -> StatV2:
    return _make_stat(
        "STR",
        "Infrastructure",
        [
            ("helm", s.helm_count),
            ("terraform", s.terraform_count),
            ("docker", s.docker_count),
        ],
    )


def _score_agi(s: SignalsV2) -> StatV2:
    return _make_stat(
        "AGI",
        "CI/CD",
        [
            ("github_actions", s.github_actions_count),
            ("gitlab_ci", s.gitlab_ci_count),
            ("jenkins", s.jenkins_count),
        ],
    )


def _score_end(s: SignalsV2) -> StatV2:
    return _make_stat(
        "END",
        "Endurance",
        [
            ("streak", _log2_level(s.longest_streak_days, 0.5)),
            ("commits", _log2_level(s.total_commit_contributions, 1.0)),
            ("prs", _log2_level(s.total_pr_contributions, 1.5)),
        ],
    )


def _score_int(s: SignalsV2) -> StatV2:
    return _make_stat(
        "INT",
        "Code",
        [
            ("python", s.python_primary_count),
            ("javascript", s.javascript_primary_count),
            ("typescript", s.typescript_primary_count),
        ],
    )


def _score_per(s: SignalsV2) -> StatV2:
    return _make_stat(
        "PER",
        "Observability",
        [
            ("prometheus", s.prometheus_count),
            ("grafana", s.grafana_count),
            ("otel", s.otel_count),
        ],
    )


def _score_cha(s: SignalsV2) -> StatV2:
    return _make_stat(
        "CHA",
        "Collaboration",
        [
            ("reviews", _log2_level(s.total_pr_review_contributions, 1.2)),
            ("issue_comments", _log2_level(s.issue_comment_event_count, 0.8)),
            ("external_repos", s.distinct_external_repos_touched),
        ],
    )


def _score_luck(s: SignalsV2) -> StatV2:
    return _make_stat(
        "LUCK",
        "AI Collaboration",
        [
            ("ai_trailers", s.ai_trailers_count),
            ("ai_configs", s.ai_configs_count),
        ],
    )
