from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from lethargy.engine.domain import RawSnapshot, Signals

ENGINE_VERSION = 1
WEEKLY_HISTOGRAM_WEEKS = 52


def extract(snapshot: RawSnapshot) -> Signals:
    profile = snapshot.profile or {}
    events = snapshot.events or []
    contrib = snapshot.contributions or {}
    gists_meta = snapshot.gists_meta or {}

    created_at = _parse_iso(profile.get("created_at"))
    account_age_days = _days_between(created_at, snapshot.fetched_at)

    event_times = [t for t in (_parse_iso(e.get("created_at")) for e in events) if t is not None]
    activity_span_days = _days_between(min(event_times), max(event_times)) if event_times else 0

    type_counts = Counter(e.get("type", "") for e in events)

    login = (profile.get("login") or "").lower()
    distinct_repos: set[str] = set()
    distinct_external: set[str] = set()
    for event in events:
        repo_name = ((event.get("repo") or {}).get("name") or "").lower()
        if not repo_name:
            continue
        distinct_repos.add(repo_name)
        owner = repo_name.split("/", 1)[0]
        if owner and owner != login:
            distinct_external.add(repo_name)

    hour_histogram = [0] * 24
    for t in event_times:
        hour_histogram[t.hour] += 1

    weekly_commits, current_streak, longest_streak = _extract_calendar(contrib)

    return Signals(
        engine_version=ENGINE_VERSION,
        account_age_days=account_age_days,
        activity_span_days=activity_span_days,
        total_commit_contributions=_to_int(contrib.get("totalCommitContributions")),
        total_pr_contributions=_to_int(contrib.get("totalPullRequestContributions")),
        total_pr_review_contributions=_to_int(contrib.get("totalPullRequestReviewContributions")),
        total_issue_contributions=_to_int(contrib.get("totalIssueContributions")),
        restricted_contribution_count=_to_int(contrib.get("restrictedContributionsCount")),
        push_event_count=type_counts.get("PushEvent", 0),
        pr_event_count=type_counts.get("PullRequestEvent", 0),
        pr_review_event_count=type_counts.get("PullRequestReviewEvent", 0),
        issue_event_count=type_counts.get("IssuesEvent", 0),
        issue_comment_event_count=type_counts.get("IssueCommentEvent", 0),
        distinct_repos_touched=len(distinct_repos),
        distinct_external_repos_touched=len(distinct_external),
        gists=_to_int(gists_meta.get("count")),
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        weekly_commits=weekly_commits,
        hour_histogram=hour_histogram,
    )


def _extract_calendar(contributions: dict) -> tuple[list[int], int, int]:
    calendar = (contributions.get("contributionCalendar") or {})
    weeks = calendar.get("weeks") or []

    days: list[tuple[datetime, int]] = []
    for week in weeks:
        for day in (week.get("contributionDays") or []):
            parsed = _parse_iso(day.get("date"))
            if parsed is None:
                continue
            days.append((parsed, _to_int(day.get("contributionCount"))))
    days.sort(key=lambda pair: pair[0])

    longest_streak = 0
    run = 0
    for _, count in days:
        if count > 0:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0

    current_streak = 0
    for _, count in reversed(days):
        if count > 0:
            current_streak += 1
        else:
            break

    weekly_commits: list[int] = []
    for week in weeks[-WEEKLY_HISTOGRAM_WEEKS:]:
        week_total = sum(
            _to_int(day.get("contributionCount")) for day in (week.get("contributionDays") or [])
        )
        weekly_commits.append(week_total)
    if len(weekly_commits) < WEEKLY_HISTOGRAM_WEEKS:
        weekly_commits = [0] * (WEEKLY_HISTOGRAM_WEEKS - len(weekly_commits)) + weekly_commits

    return weekly_commits, current_streak, longest_streak


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _days_between(a: datetime | None, b: datetime | None) -> int:
    if a is None or b is None:
        return 0
    delta = b - a
    return max(0, int(delta.total_seconds() // 86400))


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return 0
