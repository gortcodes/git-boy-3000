import json
from datetime import datetime
from pathlib import Path

from lethargy.engine.domain import RawSnapshot, Signals
from lethargy.engine.v1 import extract

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> RawSnapshot:
    data = json.loads((FIXTURES / name).read_text())
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
    return RawSnapshot(**data)


def test_extract_returns_signals_for_quiet_user():
    snap = _load("raw_quiet_user.json")
    signals = extract.extract(snap)
    assert isinstance(signals, Signals)
    assert signals.engine_version == 1
    assert signals.total_commit_contributions == 25
    assert signals.total_pr_review_contributions == 1
    assert signals.distinct_repos_touched == 2
    assert signals.distinct_external_repos_touched == 1
    assert signals.current_streak_days == 2
    assert signals.gists == 0


def test_extract_is_deterministic():
    snap = _load("raw_quiet_user.json")
    assert extract.extract(snap) == extract.extract(snap)


def test_extract_handles_active_user():
    snap = _load("raw_active_user.json")
    signals = extract.extract(snap)
    assert signals.total_commit_contributions == 850
    assert signals.distinct_repos_touched >= 3
    assert signals.distinct_external_repos_touched >= 2
    assert signals.activity_span_days >= 0
    assert sum(signals.hour_histogram) == len(snap.events)


def test_extract_weekly_commits_length_is_52():
    snap = _load("raw_quiet_user.json")
    signals = extract.extract(snap)
    assert len(signals.weekly_commits) == 52


def test_extract_longest_streak_matches_contiguous_active_days():
    snap = _load("raw_active_user.json")
    signals = extract.extract(snap)
    total_days = sum(
        1
        for week in snap.contributions["contributionCalendar"]["weeks"]
        for _ in week["contributionDays"]
    )
    # Every day in the active fixture is non-zero
    assert signals.longest_streak_days == total_days
