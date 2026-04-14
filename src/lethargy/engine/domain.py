from dataclasses import dataclass
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
