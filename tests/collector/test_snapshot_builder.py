from lethargy.collector.errors import GitHubUnavailable
from lethargy.collector.fetch import SnapshotBuilder
from lethargy.engine.domain import RawSnapshot


class _FakeGitHubClient:
    def __init__(self) -> None:
        self.profile_calls = 0
        self.events_calls = 0
        self.contributions_calls = 0
        self.repos_calls = 0
        self.tree_calls: list[tuple[str, str, str]] = []
        self.languages_calls: list[tuple[str, str]] = []
        self.fail_tree_for: set[str] = set()

    async def get_profile(self, username: str) -> dict:
        self.profile_calls += 1
        return {
            "login": username,
            "created_at": "2020-01-01T00:00:00Z",
            "public_gists": 2,
        }

    async def get_public_events(self, username: str) -> list:
        self.events_calls += 1
        return []

    async def get_contributions(self, username: str) -> dict:
        self.contributions_calls += 1
        return {
            "totalCommitContributions": 100,
            "totalPullRequestContributions": 5,
            "totalPullRequestReviewContributions": 10,
            "totalIssueContributions": 2,
            "restrictedContributionsCount": 0,
            "contributionCalendar": {"weeks": []},
        }

    async def list_user_repos(
        self, username: str, *, max_repos: int = 30
    ) -> list[dict]:
        self.repos_calls += 1
        return [
            {"full_name": f"{username}/alpha", "fork": False, "default_branch": "main"},
            {"full_name": f"{username}/beta", "fork": False, "default_branch": "main"},
        ]

    async def get_repo_tree(
        self, owner: str, name: str, branch: str
    ) -> list[str]:
        self.tree_calls.append((owner, name, branch))
        if name in self.fail_tree_for:
            raise GitHubUnavailable(f"tree failed for {name}")
        if name == "alpha":
            return ["README.md", "terraform/main.tf", "Dockerfile"]
        return ["src/app.py"]

    async def get_repo_languages(
        self, owner: str, name: str
    ) -> dict[str, int]:
        self.languages_calls.append((owner, name))
        if name == "alpha":
            return {"HCL": 2000, "Python": 500}
        return {"Python": 5000}


async def test_snapshot_builder_guest_path_leaves_v2_fields_empty():
    client = _FakeGitHubClient()
    builder = SnapshotBuilder(client)

    snap = await builder.build("guest")

    assert isinstance(snap, RawSnapshot)
    assert snap.raw_schema_version == 1
    assert snap.repos == []
    assert snap.repo_trees == {}
    assert snap.repo_languages == {}
    assert client.repos_calls == 0
    assert client.tree_calls == []
    assert client.languages_calls == []


async def test_snapshot_builder_owner_path_populates_v2_fields():
    client = _FakeGitHubClient()
    builder = SnapshotBuilder(client)

    snap = await builder.build("owner", include_repo_content=True)

    assert snap.raw_schema_version == 2
    assert len(snap.repos) == 2

    assert set(snap.repo_trees.keys()) == {"owner/alpha", "owner/beta"}
    assert "terraform/main.tf" in snap.repo_trees["owner/alpha"]
    assert "Dockerfile" in snap.repo_trees["owner/alpha"]
    assert snap.repo_trees["owner/beta"] == ["src/app.py"]

    assert snap.repo_languages["owner/alpha"]["HCL"] == 2000
    assert snap.repo_languages["owner/beta"]["Python"] == 5000

    assert client.repos_calls == 1
    assert len(client.tree_calls) == 2
    assert len(client.languages_calls) == 2


async def test_snapshot_builder_owner_path_tolerates_per_repo_failures():
    client = _FakeGitHubClient()
    client.fail_tree_for = {"beta"}  # beta's tree fetch will raise
    builder = SnapshotBuilder(client)

    snap = await builder.build("owner", include_repo_content=True)

    # Build still succeeds; beta gets an empty tree but its languages still come through.
    assert snap.raw_schema_version == 2
    assert snap.repo_trees["owner/alpha"] != []  # alpha succeeded
    assert snap.repo_trees["owner/beta"] == []  # beta tree failed, empty fallback
    assert snap.repo_languages["owner/beta"]["Python"] == 5000


async def test_snapshot_builder_skips_malformed_repo_entries():
    class _WeirdClient(_FakeGitHubClient):
        async def list_user_repos(self, username: str, *, max_repos: int = 30) -> list[dict]:
            self.repos_calls += 1
            return [
                {"full_name": "valid/repo", "fork": False, "default_branch": "main"},
                {"full_name": "no-slash", "fork": False},  # malformed
                {"full_name": 42, "fork": False},  # not a string
            ]

        async def get_repo_tree(self, owner: str, name: str, branch: str) -> list[str]:
            self.tree_calls.append((owner, name, branch))
            return ["Dockerfile"]

        async def get_repo_languages(self, owner: str, name: str) -> dict[str, int]:
            self.languages_calls.append((owner, name))
            return {"Go": 1000}

    client = _WeirdClient()
    builder = SnapshotBuilder(client)

    snap = await builder.build("odd", include_repo_content=True)

    # Only the one valid repo is probed.
    assert len(client.tree_calls) == 1
    assert client.tree_calls[0] == ("valid", "repo", "main")
    assert "valid/repo" in snap.repo_trees
