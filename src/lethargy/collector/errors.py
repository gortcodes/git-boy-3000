class GitHubError(Exception):
    """Base class for collector errors."""


class UserNotFound(GitHubError):
    """404 from a GitHub user endpoint."""


class RateLimited(GitHubError):
    """GitHub returned 403 with X-RateLimit-Remaining: 0."""

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitFloorHit(GitHubError):
    """Our internal rate-limit budget fell below the configured floor."""

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GitHubUnavailable(GitHubError):
    """Network error, 5xx, or unexpected status from GitHub."""
