from datetime import UTC, datetime

from fastapi.testclient import TestClient

from lethargy.api.app import create_app
from lethargy.api.dependencies import get_replay_service, get_sheet_service
from lethargy.engine.domain import CharacterSheet, Signals, Stat
from lethargy.services.errors import NoHistoryAvailable, UnknownEngineVersion
from lethargy.services.sheet_service import SheetBundle


def _fake_sheet() -> CharacterSheet:
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


def _fake_signals() -> Signals:
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


class _FakeSheetService:
    async def get_or_refresh(self, username: str) -> SheetBundle:
        return SheetBundle(sheet=_fake_sheet(), signals=_fake_signals())


class _FakeReplayService:
    async def recompute(self, username: str, engine_version: int) -> CharacterSheet:
        if engine_version not in (1,):
            raise UnknownEngineVersion(engine_version)
        if username.lower() != "owneruser":
            raise NoHistoryAvailable(username)
        return _fake_sheet()


def _app_with_overrides():
    app = create_app()
    app.dependency_overrides[get_sheet_service] = lambda: _FakeSheetService()
    app.dependency_overrides[get_replay_service] = lambda: _FakeReplayService()
    return app


def test_sheet_route_returns_character_sheet_json():
    with TestClient(_app_with_overrides()) as client:
        response = client.get("/v1/sheet/octocat")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "fake"
    assert body["engine_version"] == 1
    assert set(body["stats"].keys()) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
    assert body["stats"]["STR"]["value"] == 12
    assert response.headers["x-engine-version"] == "1"


def test_raw_route_includes_signals_breakdown():
    with TestClient(_app_with_overrides()) as client:
        response = client.get("/v1/sheet/octocat/raw")

    assert response.status_code == 200
    body = response.json()
    assert "signals" in body
    assert body["signals"]["total_commit_contributions"] == 100
    assert body["signals"]["distinct_repos_touched"] == 5
    assert len(body["signals"]["weekly_commits"]) == 52


def test_recompute_route_returns_sheet_for_owner():
    with TestClient(_app_with_overrides()) as client:
        response = client.post("/v1/sheet/owneruser/recompute?engine=1")

    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == 1


def test_recompute_route_returns_404_for_non_owner():
    with TestClient(_app_with_overrides()) as client:
        response = client.post("/v1/sheet/stranger/recompute?engine=1")

    assert response.status_code == 404


def test_recompute_route_returns_400_for_unknown_engine_version():
    with TestClient(_app_with_overrides()) as client:
        response = client.post("/v1/sheet/owneruser/recompute?engine=99")

    assert response.status_code == 400


def test_engine_versions_endpoint():
    with TestClient(create_app()) as client:
        response = client.get("/v1/engine/versions")
    assert response.status_code == 200
    assert response.json() == {"latest": 1, "known": [1]}
