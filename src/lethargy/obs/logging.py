import json
import logging
import sys
from datetime import UTC, datetime
from time import perf_counter

from fastapi import FastAPI, Request
from opentelemetry.trace import get_current_span
from starlette.middleware.base import BaseHTTPMiddleware

from lethargy.config import Settings

ACCESS_LOGGER_NAME = "lethargy.access"
SKIP_ACCESS_LOG_PATHS = frozenset({"/metrics", "/healthz"})


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }

        span = get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx is not None and ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")

        extras = getattr(record, "extra_fields", None)
        if isinstance(extras, dict):
            payload.update(extras)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure(settings: Settings) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._logger = logging.getLogger(ACCESS_LOGGER_NAME)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_ACCESS_LOG_PATHS:
            return await call_next(request)

        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000

        route_obj = request.scope.get("route")
        route_template = getattr(route_obj, "path", request.url.path)

        fields: dict[str, object] = {
            "method": request.method,
            "route": route_template,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if request.client is not None:
            fields["remote_addr"] = request.client.host

        path_params = request.scope.get("path_params") or {}
        if "username" in path_params:
            fields["username"] = path_params["username"]

        self._logger.info(
            "%s %s %d %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"extra_fields": fields},
        )
        return response


def instrument(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)
