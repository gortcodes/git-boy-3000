from datetime import UTC, datetime

from fastapi.testclient import TestClient

from lethargy.api.app import create_app
from lethargy.api.dependencies import get_replay_service, get_sheet_service
from lethargy.engine.domain import (
    CharacterSheet,
    CharacterSheetV2,
    SheetBundle,
    SheetBundleV2,
    Signals,
    SignalsV2,
    Stat,
    StatV2,
    SubStatV2,
)
from lethargy.services.errors import NoHistoryAvailable, UnknownEngineVersion
from lethargy.services.sheet_service import SheetEnvelope


def _fake_sheet_v1() -> CharacterSheet:
    return CharacterSheet(
        username="fake",
        engine_version=1,
        raw_schema_version=1,
        fetched_at=datetime(2026, 4, 14, tzinfo=UTC),
        computed_at=datetime(2026, 4, 14, tzinfo=UTC),
        stats={
            "STR": Stat("STR", 12, 12.3, {"total_commit_contributions": 100.0}),
            "DEX": Stat("DEX", 10, 9.8, {"events_per_day": 5.0}),
            "CON": Stat("CON", 8, 8.1, {}),
            "INT": Stat("INT", 11, 11.0, {}),
            "WIS": Stat("WIS", 15, 14.9, {}),
            "CHA": Stat("CHA", 9, 9.2, {}),
        },
        flavor={"account_age_days": 365},
    )


def _fake_signals_v1() -> Signals:
    return Signals(
        engine_version=1,
        account_age_days=365,
        activity_span_days=30,
        total_commit_contributions=100,
        total_pr_contributions=10,
        total_pr_review_contributions=5,
        total_issue_contributions=3,
        restricted_contribution_count=0,
        push_event_count=10,
        pr_event_count=5,
        pr_review_event_count=3,
        issue_event_count=2,
        issue_comment_event_count=4,
        distinct_repos_touched=5,
        distinct_external_repos_touched=2,
        gists=0,
        current_streak_days=7,
        longest_streak_days=30,
        weekly_commits=[0] * 52,
        hour_histogram=[0] * 24,
    )


def _fake_v1_envelope(status: str = "miss") -> SheetEnvelope:
    return SheetEnvelope(
        bundle=SheetBundle(sheet=_fake_sheet_v1(), signals=_fake_signals_v1()),
        cache_status=status,
    )


def _fake_sheet_v2() -> CharacterSheetV2:
    stats: dict[str, StatV2] = {}
    for name, level in [
        ("STR", 4),
        ("AGI", 3),
        ("END", 8),
        ("INT", 2),
        ("PER", 1),
        ("CHA", 6),
        ("LUCK", 1),
    ]:
        stats[name] = StatV2(
            name=name,
            display=name.lower(),
            level=level,
            sub_stats=[
                SubStatV2(name="alpha", level=level // 2),
                SubStatV2(name="beta", level=level - level // 2),
            ],
        )
    character_level = sum(s.level for s in stats.values())
    return CharacterSheetV2(
        username="owneruser",
        engine_version=2,
        raw_schema_version=2,
        fetched_at=datetime(2026, 4, 15, tzinfo=UTC),
        computed_at=datetime(2026, 4, 15, tzinfo=UTC),
        class_name="SRE",
        character_level=character_level,
        stats=stats,
        flavor={
            "account_age_days": 2000,
            "activity_span_days": 90,
            "current_streak_days": 12,
            "longest_streak_days": 45,
            "weekly_active_weeks": 40,
            "hour_histogram": [0] * 24,
        },
    )


def _fake_signals_v2() -> SignalsV2:
    return SignalsV2(
        engine_version=2,
        helm_count=1,
        terraform_count=1,
        docker_count=2,
        github_actions_count=2,
        gitlab_ci_count=0,
        jenkins_count=0,
        longest_streak_days=45,
        total_commit_contributions=500,
        total_pr_contributions=30,
        python_primary_count=1,
        javascript_primary_count=0,
        typescript_primary_count=0,
        prometheus_count=1,
        grafana_count=0,
        otel_count=0,
        total_pr_review_contributions=75,
        issue_comment_event_count=1,
        distinct_external_repos_touched=2,
        ai_trailers_count=1,
        ai_configs_count=1,
        account_age_days=2000,
        activity_span_days=90,
        current_streak_days=12,
        weekly_active_weeks=40,
        hour_histogram=[0] * 24,
    )


def _fake_v2_envelope(status: str = "miss") -> SheetEnvelope:
    return SheetEnvelope(
        bundle=SheetBundleV2(sheet=_fake_sheet_v2(), signals=_fake_signals_v2()),
        cache_status=status,
    )


class _FakeV1SheetService:
    def __init__(self) -> None:
        self.force_calls = 0

    async def get_or_refresh(self, username: str, *, force: bool = False) -> SheetEnvelope:
        if force:
            self.force_calls += 1
            return _fake_v1_envelope("forced")
        return _fake_v1_envelope("miss")


class _FakeV2SheetService:
    async def get_or_refresh(self, username: str, *, force: bool = False) -> SheetEnvelope:
        return _fake_v2_envelope()


class _FakeReplayService:
    async def recompute(self, username: str, engine_version: int) -> CharacterSheet:
        if engine_version not in (1,):
            raise UnknownEngineVersion(engine_version)
        if username.lower() != "owneruser":
            raise NoHistoryAvailable(username)
        return _fake_sheet_v1()


def _app_with_v1_overrides() -> tuple:
    app = create_app()
    fake = _FakeV1SheetService()
    app.dependency_overrides[get_sheet_service] = lambda: fake
    app.dependency_overrides[get_replay_service] = lambda: _FakeReplayService()
    return app, fake


def _app_with_v2_overrides():
    app = create_app()
    app.dependency_overrides[get_sheet_service] = lambda: _FakeV2SheetService()
    app.dependency_overrides[get_replay_service] = lambda: _FakeReplayService()
    return app


def test_sheet_route_returns_v1_character_sheet_json():
    app, _ = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.get("/v1/sheet/octocat")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "fake"
    assert body["engine_version"] == 1
    assert set(body["stats"].keys()) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
    assert body["stats"]["STR"]["value"] == 12
    assert response.headers["x-engine-version"] == "1"
    assert response.headers["x-cache-status"] == "miss"


def test_sheet_route_force_flag_reaches_service():
    app, fake = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.get("/v1/sheet/octocat?force=true")

    assert response.status_code == 200
    assert response.headers["x-cache-status"] == "forced"
    assert fake.force_calls == 1


def test_raw_route_includes_v1_signals_breakdown():
    app, _ = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.get("/v1/sheet/octocat/raw")

    assert response.status_code == 200
    body = response.json()
    assert "signals" in body
    assert body["signals"]["total_commit_contributions"] == 100
    assert body["signals"]["distinct_repos_touched"] == 5
    assert len(body["signals"]["weekly_commits"]) == 52


def test_sheet_route_serializes_v2_bundle():
    app = _app_with_v2_overrides()
    with TestClient(app) as client:
        response = client.get("/v1/sheet/owneruser")

    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == 2
    assert body["class_name"] == "SRE"
    assert body["character_level"] > 0
    assert set(body["stats"].keys()) == {"STR", "AGI", "END", "INT", "PER", "CHA", "LUCK"}
    assert "sub_stats" in body["stats"]["STR"]
    assert body["stats"]["STR"]["display"] == "str"
    assert response.headers["x-engine-version"] == "2"


def test_raw_route_includes_v2_signals():
    app = _app_with_v2_overrides()
    with TestClient(app) as client:
        response = client.get("/v1/sheet/owneruser/raw")

    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == 2
    assert "signals" in body
    assert body["signals"]["helm_count"] == 1
    assert body["signals"]["terraform_count"] == 1
    assert body["signals"]["ai_trailers_count"] == 1


def test_recompute_route_returns_sheet_for_owner():
    app, _ = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.post("/v1/sheet/owneruser/recompute?engine=1")

    assert response.status_code == 200
    assert response.json()["engine_version"] == 1


def test_recompute_route_returns_404_for_non_owner():
    app, _ = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.post("/v1/sheet/stranger/recompute?engine=1")

    assert response.status_code == 404


def test_recompute_route_returns_400_for_unknown_engine_version():
    app, _ = _app_with_v1_overrides()
    with TestClient(app) as client:
        response = client.post("/v1/sheet/owneruser/recompute?engine=99")

    assert response.status_code == 400


def test_engine_versions_endpoint():
    with TestClient(create_app()) as client:
        response = client.get("/v1/engine/versions")
    assert response.status_code == 200
    assert response.json() == {"latest": 2, "known": [1, 2]}
