import json
import math
from datetime import UTC, datetime
from pathlib import Path

from lethargy.engine.domain import CharacterSheetV2, RawSnapshot
from lethargy.engine.v2 import extract, score

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_STATS = {"STR", "AGI", "END", "INT", "PER", "CHA", "LUCK"}


def _load(name: str) -> RawSnapshot:
    data = json.loads((FIXTURES / name).read_text())
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
    return RawSnapshot(**data)


def _run(name: str) -> CharacterSheetV2:
    snap = _load(name)
    signals = extract.extract(snap)
    return score.score(
        signals,
        username=snap.username,
        class_name="SRE",
        fetched_at=snap.fetched_at,
        computed_at=datetime(2026, 4, 15, tzinfo=UTC),
        raw_schema_version=snap.raw_schema_version,
    )


def test_score_v2_returns_character_sheet_v2():
    sheet = _run("raw_owner_v2.json")
    assert isinstance(sheet, CharacterSheetV2)
    assert sheet.engine_version == 2
    assert sheet.class_name == "SRE"


def test_score_v2_stat_keys_match_spec():
    sheet = _run("raw_owner_v2.json")
    assert set(sheet.stats.keys()) == EXPECTED_STATS


def test_score_v2_stat_levels_are_sums_of_sub_stats_with_floor_of_one():
    sheet = _run("raw_owner_v2.json")
    for name, stat in sheet.stats.items():
        sub_sum = sum(sub.level for sub in stat.sub_stats)
        expected = max(1, sub_sum)
        assert stat.level == expected, f"{name}: {stat.level} != max(1, {sub_sum})"


def test_score_v2_str_sub_stats():
    sheet = _run("raw_owner_v2.json")
    sub = {s.name: s.level for s in sheet.stats["STR"].sub_stats}
    assert sub == {"helm": 1, "terraform": 1, "docker": 2}
    assert sheet.stats["STR"].level == 4


def test_score_v2_end_uses_log2_with_weights():
    sheet = _run("raw_owner_v2.json")
    sub = {s.name: s.level for s in sheet.stats["END"].sub_stats}
    # streak = round(log2(10+1) * 0.5)
    assert sub["streak"] == round(math.log2(11) * 0.5)
    # commits = round(log2(500+1) * 1.0)
    assert sub["commits"] == round(math.log2(501) * 1.0)
    # prs = round(log2(30+1) * 1.5)
    assert sub["prs"] == round(math.log2(31) * 1.5)


def test_score_v2_cha_uses_log2_for_reviews_and_comments_but_raw_external_repos():
    sheet = _run("raw_owner_v2.json")
    sub = {s.name: s.level for s in sheet.stats["CHA"].sub_stats}
    assert sub["reviews"] == round(math.log2(76) * 1.2)
    assert sub["issue_comments"] == round(math.log2(2) * 0.8)
    assert sub["external_repos"] == 2  # raw


def test_score_v2_luck_counts_raw():
    sheet = _run("raw_owner_v2.json")
    sub = {s.name: s.level for s in sheet.stats["LUCK"].sub_stats}
    assert sub == {"ai_trailers": 1, "ai_configs": 1}
    assert sheet.stats["LUCK"].level == 2


def test_score_v2_character_level_is_sum_of_stat_levels():
    sheet = _run("raw_owner_v2.json")
    expected = sum(stat.level for stat in sheet.stats.values())
    assert sheet.character_level == expected
    # Sanity: non-trivial
    assert sheet.character_level > 20


def test_score_v2_is_deterministic():
    assert _run("raw_owner_v2.json") == _run("raw_owner_v2.json")


def test_score_v2_empty_signals_floor_every_stat_at_one():
    from lethargy.engine.domain import SignalsV2

    empty = SignalsV2(
        engine_version=2,
        helm_count=0,
        terraform_count=0,
        docker_count=0,
        github_actions_count=0,
        gitlab_ci_count=0,
        jenkins_count=0,
        longest_streak_days=0,
        total_commit_contributions=0,
        total_pr_contributions=0,
        python_primary_count=0,
        javascript_primary_count=0,
        typescript_primary_count=0,
        prometheus_count=0,
        grafana_count=0,
        otel_count=0,
        total_pr_review_contributions=0,
        issue_comment_event_count=0,
        distinct_external_repos_touched=0,
        ai_trailers_count=0,
        ai_configs_count=0,
        account_age_days=0,
        activity_span_days=0,
        current_streak_days=0,
        weekly_active_weeks=0,
        hour_histogram=[0] * 24,
    )
    sheet = score.score(
        empty,
        username="empty",
        class_name="Engineer",
        fetched_at=datetime(2026, 4, 15, tzinfo=UTC),
        computed_at=datetime(2026, 4, 15, tzinfo=UTC),
        raw_schema_version=2,
    )
    for name, stat in sheet.stats.items():
        assert stat.level >= 1, f"{name}: level {stat.level} below floor"
    # Seven parent stats, each floored at 1
    assert sheet.character_level == 7


def test_score_v2_class_name_is_passed_through():
    snap = _load("raw_owner_v2.json")
    signals = extract.extract(snap)
    sheet = score.score(
        signals,
        username="alt",
        class_name="Platform Engineer",
        fetched_at=snap.fetched_at,
        computed_at=datetime(2026, 4, 15, tzinfo=UTC),
        raw_schema_version=2,
    )
    assert sheet.class_name == "Platform Engineer"
    assert sheet.username == "alt"
