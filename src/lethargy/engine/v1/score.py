from __future__ import annotations

import math
from datetime import datetime
from statistics import mean, pstdev

from lethargy.engine.domain import CharacterSheet, Signals, Stat

ENGINE_VERSION = 1


def score(
    signals: Signals,
    *,
    username: str,
    fetched_at: datetime,
    computed_at: datetime,
    raw_schema_version: int,
) -> CharacterSheet:
    stats = {
        "STR": _score_str(signals),
        "DEX": _score_dex(signals),
        "CON": _score_con(signals),
        "INT": _score_int(signals),
        "WIS": _score_wis(signals),
        "CHA": _score_cha(signals),
    }
    flavor = {
        "account_age_days": signals.account_age_days,
        "activity_span_days": signals.activity_span_days,
        "current_streak_days": signals.current_streak_days,
        "longest_streak_days": signals.longest_streak_days,
        "hour_histogram": list(signals.hour_histogram),
        "weekly_commits": list(signals.weekly_commits),
        "restricted_contribution_count": signals.restricted_contribution_count,
    }
    return CharacterSheet(
        username=username,
        engine_version=ENGINE_VERSION,
        raw_schema_version=raw_schema_version,
        fetched_at=fetched_at,
        computed_at=computed_at,
        stats=stats,
        flavor=flavor,
    )


def _clamp(raw: float) -> int:
    if math.isnan(raw) or math.isinf(raw):
        return 1
    return max(1, min(20, round(raw)))


def _score_str(s: Signals) -> Stat:
    raw = math.log10(max(s.total_commit_contributions, 0) + 1) * 6
    return Stat(
        name="STR",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "total_commit_contributions": float(s.total_commit_contributions),
        },
    )


def _score_dex(s: Signals) -> Stat:
    span = max(1, s.activity_span_days)
    total_events = (
        s.push_event_count
        + s.pr_event_count
        + s.pr_review_event_count
        + s.issue_event_count
        + s.issue_comment_event_count
    )
    event_rate = total_events / span
    raw = event_rate * 2 + s.current_streak_days / 30
    return Stat(
        name="DEX",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "events_per_day": event_rate,
            "current_streak_days": float(s.current_streak_days),
        },
    )


def _score_con(s: Signals) -> Stat:
    span_weeks = max(s.activity_span_days, 0) / 7
    weekly = s.weekly_commits
    if len(weekly) >= 2 and any(weekly):
        mu = mean(weekly)
        sigma = pstdev(weekly)
        steadiness = 1.0 / (1.0 + sigma / max(mu, 1.0))
    else:
        steadiness = 0.0
    raw = span_weeks / 4 + steadiness * 10
    return Stat(
        name="CON",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "activity_span_days": float(s.activity_span_days),
            "steadiness": steadiness,
        },
    )


def _score_int(s: Signals) -> Stat:
    raw = math.log2(max(s.distinct_repos_touched, 0) + 1) * 3 + s.gists
    return Stat(
        name="INT",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "distinct_repos_touched": float(s.distinct_repos_touched),
            "gists": float(s.gists),
        },
    )


def _score_wis(s: Signals) -> Stat:
    age_component = math.sqrt(max(s.account_age_days, 0) / 30)
    written = max(1, s.total_commit_contributions + s.total_pr_contributions)
    review_ratio = s.total_pr_review_contributions / written
    raw = age_component + review_ratio * 8
    return Stat(
        name="WIS",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "account_age_days": float(s.account_age_days),
            "review_ratio": review_ratio,
        },
    )


def _score_cha(s: Signals) -> Stat:
    external = s.distinct_external_repos_touched * 2
    comments = (s.total_pr_review_contributions + s.issue_comment_event_count) / 4
    raw = external + comments
    return Stat(
        name="CHA",
        value=_clamp(raw),
        raw_score=raw,
        contributing_signals={
            "distinct_external_repos_touched": float(s.distinct_external_repos_touched),
            "pr_reviews": float(s.total_pr_review_contributions),
            "issue_comments": float(s.issue_comment_event_count),
        },
    )
