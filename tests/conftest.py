import os

os.environ.setdefault(
    "LETHARGY_DB_URL",
    "postgresql+asyncpg://lethargy:lethargy@localhost:5432/lethargy_test",
)
os.environ.setdefault("LETHARGY_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("LETHARGY_OTEL_EXPORTER_OTLP_ENDPOINT", "")
os.environ.setdefault("LETHARGY_ENV", "test")
