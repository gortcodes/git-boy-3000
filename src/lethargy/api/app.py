from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from lethargy.api.routes import health, sheet
from lethargy.cache.github_etag import GitHubEtagCache
from lethargy.cache.redis import RedisClient
from lethargy.collector.client import GitHubClient
from lethargy.config import Settings, get_settings
from lethargy.obs import logging as obs_logging
from lethargy.obs import metrics as obs_metrics
from lethargy.obs import tracing as obs_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()

    http = httpx.AsyncClient(timeout=10.0)
    redis_client = RedisClient.from_settings(settings)
    etag_cache = GitHubEtagCache(redis_client)
    github_client = GitHubClient(
        settings=settings,
        http=http,
        etag_cache=etag_cache,
    )

    app.state.http_client = http
    app.state.redis_client = redis_client
    app.state.github_client = github_client

    try:
        yield
    finally:
        await http.aclose()
        await redis_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    obs_logging.configure(settings)

    app = FastAPI(title="lethargy", version="0.1.0", lifespan=lifespan)

    obs_metrics.instrument(app)
    obs_tracing.instrument(app, settings)

    app.include_router(health.router)
    app.include_router(sheet.router)
    return app
