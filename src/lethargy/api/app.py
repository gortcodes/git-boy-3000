from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lethargy.api.routes import engine, health, sheet
from lethargy.cache.github_etag import GitHubEtagCache
from lethargy.cache.lock import Lock
from lethargy.cache.redis import RedisClient
from lethargy.cache.sheet import SheetCache
from lethargy.cache.throttle import Throttle
from lethargy.collector.client import GitHubClient
from lethargy.collector.fetch import SnapshotBuilder
from lethargy.collector.rate_limit import RateLimitState
from lethargy.config import Settings, get_settings
from lethargy.obs import logging as obs_logging
from lethargy.obs import metrics as obs_metrics
from lethargy.obs import tracing as obs_tracing
from lethargy.persistence.db import Database
from lethargy.services.replay_service import ReplayService
from lethargy.services.sheet_service import SheetService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()

    http = httpx.AsyncClient(timeout=10.0)
    redis_client = RedisClient.from_settings(settings)
    etag_cache = GitHubEtagCache(redis_client)
    rate_limit_state = RateLimitState(floor=settings.rate_limit_floor)
    github_client = GitHubClient(
        settings=settings,
        http=http,
        etag_cache=etag_cache,
        rate_limit_state=rate_limit_state,
    )
    snapshot_builder = SnapshotBuilder(github_client)
    database = Database.from_settings(settings)
    sheet_cache = SheetCache(redis_client)
    lock = Lock(redis_client)
    throttle = Throttle(redis_client, ttl_seconds=settings.refresh_throttle_seconds)
    sheet_service = SheetService(
        snapshot_builder=snapshot_builder,
        sheet_cache=sheet_cache,
        lock=lock,
        throttle=throttle,
        owner_usernames=settings.owner_usernames,
        fresh_ttl_seconds=settings.sheet_fresh_ttl_seconds,
        stale_ttl_seconds=settings.sheet_stale_ttl_seconds,
        owner_class=settings.owner_class,
    )
    replay_service = ReplayService(
        database=database,
        owner_usernames=settings.owner_usernames,
        owner_class=settings.owner_class,
    )

    app.state.settings = settings
    app.state.http_client = http
    app.state.redis_client = redis_client
    app.state.rate_limit_state = rate_limit_state
    app.state.github_client = github_client
    app.state.snapshot_builder = snapshot_builder
    app.state.database = database
    app.state.sheet_cache = sheet_cache
    app.state.lock = lock
    app.state.throttle = throttle
    app.state.sheet_service = sheet_service
    app.state.replay_service = replay_service

    try:
        yield
    finally:
        await http.aclose()
        await redis_client.close()
        await database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    obs_logging.configure(settings)

    app = FastAPI(title="lethargy", version="0.1.0", lifespan=lifespan)

    obs_metrics.instrument(app)
    obs_tracing.instrument(app, settings)
    obs_logging.instrument(app)

    app.include_router(health.router)
    app.include_router(sheet.router)
    app.include_router(engine.router)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app
