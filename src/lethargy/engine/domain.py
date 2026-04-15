from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RawSnapshot:
    username: str
    fetched_at: datetime
    raw_schema_version: int
    profile: dict
    events: list[dict]
    contributions: dict
    gists_meta: dict
    # v2 additions — empty for v1/non-owner snapshots
    repos: list[dict] = field(default_factory=list)
    repo_trees: dict[str, list[str]] = field(default_factory=dict)
    repo_languages: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class Signals:
    engine_version: int
    account_age_days: int
    activity_span_days: int
    total_commit_contributions: int
    total_pr_contributions: int
    total_pr_review_contributions: int
    total_issue_contributions: int
    restricted_contribution_count: int
    push_event_count: int
    pr_event_count: int
    pr_review_event_count: int
    issue_event_count: int
    issue_comment_event_count: int
    distinct_repos_touched: int
    distinct_external_repos_touched: int
    gists: int
    current_streak_days: int
    longest_streak_days: int
    weekly_commits: list[int]
    hour_histogram: list[int]


@dataclass(frozen=True)
class Stat:
    name: str
    value: int
    raw_score: float
    contributing_signals: dict[str, float]


@dataclass(frozen=True)
class CharacterSheet:
    username: str
    engine_version: int
    raw_schema_version: int
    fetched_at: datetime
    computed_at: datetime
    stats: dict[str, Stat]
    flavor: dict


@dataclass(frozen=True)
class SheetBundle:
    sheet: CharacterSheet
    signals: Signals


# === Engine v2 types ===


@dataclass(frozen=True)
class SubStatV2:
    name: str
    level: int


@dataclass(frozen=True)
class StatV2:
    name: str
    display: str
    level: int
    sub_stats: list[SubStatV2]


@dataclass(frozen=True)
class SignalsV2:
    engine_version: int
    # STR / Infrastructure
    helm_count: int
    terraform_count: int
    docker_count: int
    # AGI / CI/CD
    github_actions_count: int
    gitlab_ci_count: int
    jenkins_count: int
    # END raw inputs (log2 weighting applied in score)
    longest_streak_days: int
    total_commit_contributions: int
    total_pr_contributions: int
    # INT / Code
    python_primary_count: int
    javascript_primary_count: int
    typescript_primary_count: int
    # PER / Observability
    prometheus_count: int
    grafana_count: int
    otel_count: int
    # CHA raw inputs (log2 for reviews/comments, raw for external_repos)
    total_pr_review_contributions: int
    issue_comment_event_count: int
    distinct_external_repos_touched: int
    # LUCK / AI collaboration
    ai_trailers_count: int
    ai_configs_count: int
    # Behavioral flavor (not scored)
    account_age_days: int
    activity_span_days: int
    current_streak_days: int
    weekly_active_weeks: int
    hour_histogram: list[int]


@dataclass(frozen=True)
class CharacterSheetV2:
    username: str
    engine_version: int
    raw_schema_version: int
    fetched_at: datetime
    computed_at: datetime
    class_name: str
    character_level: int
    stats: dict[str, StatV2]
    flavor: dict


@dataclass(frozen=True)
class SheetBundleV2:
    sheet: CharacterSheetV2
    signals: SignalsV2
