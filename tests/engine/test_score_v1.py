import json
from datetime import UTC, datetime
from pathlib import Path

from lethargy.engine.domain import CharacterSheet, RawSnapshot
from lethargy.engine.v1 import extract, score

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_STATS = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}


def _load(name: str) -> RawSnapshot:
    data = json.loads((FIXTURES / name).read_text())
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
    return RawSnapshot(**data)


def _run(name: str) -> CharacterSheet:
    snap = _load(name)
    signals = extract.extract(snap)
    return score.score(
        signals,
        username=snap.username,
        fetched_at=snap.fetched_at,
        computed_at=datetime(2026, 4, 14, tzinfo=UTC),
        raw_schema_version=snap.raw_schema_version,
    )


def test_score_returns_character_sheet_for_quiet_user():
    sheet = _run("raw_quiet_user.json")
    assert isinstance(sheet, CharacterSheet)
    assert sheet.engine_version == 1
    assert sheet.raw_schema_version == 1
    assert set(sheet.stats.keys()) == EXPECTED_STATS


def test_score_all_stats_within_range_quiet():
    sheet = _run("raw_quiet_user.json")
    for stat in sheet.stats.values():
        assert 1 <= stat.value <= 20, f"{stat.name} = {stat.value}"


def test_score_all_stats_within_range_active():
    sheet = _run("raw_active_user.json")
    for stat in sheet.stats.values():
        assert 1 <= stat.value <= 20, f"{stat.name} = {stat.value}"


def test_score_is_deterministic():
    assert _run("raw_quiet_user.json") == _run("raw_quiet_user.json")


def test_active_user_has_stronger_commit_signal_than_quiet():
    quiet = _run("raw_quiet_user.json")
    active = _run("raw_active_user.json")
    assert active.stats["STR"].value > quiet.stats["STR"].value
