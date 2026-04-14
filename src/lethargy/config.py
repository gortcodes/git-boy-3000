import os
from dataclasses import dataclass
from functools import lru_cache


def _parse_usernames(raw: str) -> frozenset[str]:
    return frozenset(u.strip().lower() for u in raw.split(",") if u.strip())


def _required(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"missing required env var: {key}")
    return value


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


@dataclass(frozen=True)
class Settings:
    owner_usernames: frozenset[str]
    github_token: str
    db_url: str
    redis_url: str
    sheet_fresh_ttl_seconds: int
    sheet_stale_ttl_seconds: int
    refresh_throttle_seconds: int
    rate_limit_floor: int
    otel_exporter_otlp_endpoint: str | None
    log_level: str
    env: str

    @classmethod
    def from_env(cls) -> "Settings":
        otlp = os.environ.get("LETHARGY_OTEL_EXPORTER_OTLP_ENDPOINT") or None
        return cls(
            owner_usernames=_parse_usernames(_env("LETHARGY_OWNER_USERNAMES", "")),
            github_token=_env("LETHARGY_GITHUB_TOKEN", ""),
            db_url=_required("LETHARGY_DB_URL"),
            redis_url=_required("LETHARGY_REDIS_URL"),
            sheet_fresh_ttl_seconds=_env_int("LETHARGY_SHEET_FRESH_TTL_SECONDS", 600),
            sheet_stale_ttl_seconds=_env_int("LETHARGY_SHEET_STALE_TTL_SECONDS", 3000),
            refresh_throttle_seconds=_env_int("LETHARGY_REFRESH_THROTTLE_SECONDS", 600),
            rate_limit_floor=_env_int("LETHARGY_RATE_LIMIT_FLOOR", 500),
            otel_exporter_otlp_endpoint=otlp,
            log_level=_env("LETHARGY_LOG_LEVEL", "INFO"),
            env=_env("LETHARGY_ENV", "dev"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
