import json
from datetime import datetime
from pathlib import Path

from lethargy.engine.domain import RawSnapshot, SignalsV2
from lethargy.engine.v2 import extract

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> RawSnapshot:
    data = json.loads((FIXTURES / name).read_text())
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
    return RawSnapshot(**data)


def test_extract_v2_returns_signals_v2():
    snap = _load("raw_owner_v2.json")
    signals = extract.extract(snap)
    assert isinstance(signals, SignalsV2)
    assert signals.engine_version == 2


def test_extract_v2_infra_counts():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.helm_count == 1
    assert signals.terraform_count == 1
    assert signals.docker_count == 2


def test_extract_v2_cicd_counts():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.github_actions_count == 2
    assert signals.gitlab_ci_count == 1
    assert signals.jenkins_count == 1


def test_extract_v2_observability_counts():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.prometheus_count == 1
    assert signals.grafana_count == 1
    assert signals.otel_count == 1


def test_extract_v2_language_primary_counts():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.python_primary_count == 1
    assert signals.javascript_primary_count == 0
    assert signals.typescript_primary_count == 0


def test_extract_v2_luck_counts():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.ai_trailers_count == 1
    assert signals.ai_configs_count == 1


def test_extract_v2_reuses_v1_behavioral_signals():
    signals = extract.extract(_load("raw_owner_v2.json"))
    assert signals.total_commit_contributions == 500
    assert signals.total_pr_contributions == 30
    assert signals.total_pr_review_contributions == 75
    assert signals.issue_comment_event_count == 1
    assert signals.distinct_external_repos_touched == 2
    assert signals.longest_streak_days == 10


def test_extract_v2_is_deterministic():
    snap = _load("raw_owner_v2.json")
    assert extract.extract(snap) == extract.extract(snap)


def test_extract_v2_empty_repos_yields_zero_infra_counts():
    snap = RawSnapshot(
        username="guest",
        fetched_at=datetime.fromisoformat("2026-04-15T00:00:00+00:00"),
        raw_schema_version=1,
        profile={"login": "guest", "created_at": "2024-01-01T00:00:00Z"},
        events=[],
        contributions={},
        gists_meta={"count": 0},
    )
    signals = extract.extract(snap)
    assert signals.helm_count == 0
    assert signals.terraform_count == 0
    assert signals.docker_count == 0
    assert signals.ai_trailers_count == 0
    assert signals.ai_configs_count == 0
