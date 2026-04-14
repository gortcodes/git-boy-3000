class ReplayError(Exception):
    """Base for replay-service errors."""


class UnknownEngineVersion(ReplayError):
    """Requested engine version is not registered."""


class NoHistoryAvailable(ReplayError):
    """No persisted snapshot exists for this user (or user is not an owner)."""
