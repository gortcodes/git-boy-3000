from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from lethargy.obs.names import (
    METRIC_COLLECTOR_GITHUB_DURATION_SECONDS,
    METRIC_COLLECTOR_GITHUB_REQUESTS_TOTAL,
    METRIC_ENGINE_VERSION_INFO,
    METRIC_GITHUB_RATE_LIMIT_REMAINING,
    METRIC_GITHUB_RATE_LIMIT_RESET_SECONDS,
    METRIC_HTTP_REQUEST_DURATION_SECONDS,
    METRIC_HTTP_REQUESTS_TOTAL,
    METRIC_OWNER_SNAPSHOTS_TOTAL,
    METRIC_SHEET_CACHE_RESULT_TOTAL,
    METRIC_SHEET_ENGINE_COMPUTE_SECONDS,
)

registry = CollectorRegistry()

http_requests_total = Counter(
    METRIC_HTTP_REQUESTS_TOTAL,
    "Total HTTP requests",
    labelnames=("route", "status"),
    registry=registry,
)
http_request_duration_seconds = Histogram(
    METRIC_HTTP_REQUEST_DURATION_SECONDS,
    "HTTP request duration (seconds)",
    labelnames=("route",),
    registry=registry,
)
sheet_cache_result_total = Counter(
    METRIC_SHEET_CACHE_RESULT_TOTAL,
    "Sheet cache resolution result",
    labelnames=("result",),
    registry=registry,
)
sheet_engine_compute_seconds = Histogram(
    METRIC_SHEET_ENGINE_COMPUTE_SECONDS,
    "Engine compute duration (seconds)",
    labelnames=("version",),
    registry=registry,
)
collector_github_requests_total = Counter(
    METRIC_COLLECTOR_GITHUB_REQUESTS_TOTAL,
    "GitHub API requests made by the collector",
    labelnames=("endpoint", "status", "cache"),
    registry=registry,
)
collector_github_duration_seconds = Histogram(
    METRIC_COLLECTOR_GITHUB_DURATION_SECONDS,
    "GitHub API call duration (seconds)",
    labelnames=("endpoint",),
    registry=registry,
)
github_rate_limit_remaining = Gauge(
    METRIC_GITHUB_RATE_LIMIT_REMAINING,
    "GitHub API rate limit remaining",
    registry=registry,
)
github_rate_limit_reset_seconds = Gauge(
    METRIC_GITHUB_RATE_LIMIT_RESET_SECONDS,
    "Seconds until GitHub rate limit reset",
    registry=registry,
)
owner_snapshots_total = Counter(
    METRIC_OWNER_SNAPSHOTS_TOTAL,
    "Snapshots persisted for owner usernames",
    labelnames=("username",),
    registry=registry,
)
engine_version_info = Gauge(
    METRIC_ENGINE_VERSION_INFO,
    "Engine version indicator",
    labelnames=("version",),
    registry=registry,
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        start = perf_counter()
        response = await call_next(request)
        duration = perf_counter() - start

        route = _route_template(request)
        http_requests_total.labels(route=route, status=str(response.status_code)).inc()
        http_request_duration_seconds.labels(route=route).observe(duration)
        return response


def instrument(app: FastAPI) -> None:
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
