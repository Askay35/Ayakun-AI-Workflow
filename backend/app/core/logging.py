"""JSON-логи в stdout для Loki/Promtail + перехват HTTP."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Any, Callable
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
}

logger = logging.getLogger("ayakun.http")
_HTTP_LOGGING_INSTALLED = False


_BOT_PATH_RE = re.compile(r"/bot[^/\s]+", re.I)
_BOT_TOKEN_RE = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b")


def redact_secrets(value: str) -> str:
    """Убирает токен бота из строк логов и сообщений об ошибках."""
    text = _BOT_PATH_RE.sub("/bot[redacted]", value)
    return _BOT_TOKEN_RE.sub("[redacted]", text)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return redact_secrets(str(value))


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "logger": record.name,
            "msg": redact_secrets(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = redact_secrets(self.formatException(record.exc_info))
        for key, value in record.__dict__.items():
            if key in RESERVED or key.startswith("_"):
                continue
            payload[key] = jsonable(value)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    # Не затираем уже настроенный сервис (uvicorn backend), если Celery импортируется в том же процессе.
    existing = next((h for h in root.handlers if isinstance(h.formatter, JsonFormatter)), None)
    if existing is not None and getattr(existing.formatter, "service", None) not in {None, service}:
        install_outbound_http_logging()
        return
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True
    install_outbound_http_logging()


def output_preview(output: object, limit: int = 2000) -> str:
    payload: object = output
    if isinstance(output, dict) and "text" in output:
        payload = {
            "text": output.get("text"),
            "model": output.get("model"),
            "truncated": output.get("truncated"),
            "usage": output.get("usage"),
        }
    raw = json.dumps(jsonable(payload), ensure_ascii=False)
    if len(raw) > limit:
        return raw[:limit] + "…"
    return raw


def sanitize_url(url: object) -> str:
    """Хост + path без query и без токена бота в path."""
    raw = str(getattr(url, "url", None) or url or "")
    parts = urlsplit(raw)
    path = _BOT_PATH_RE.sub("/bot[redacted]", parts.path or "/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


_BODY_LIMIT = 4000
_SECRET_JSON_RE = re.compile(
    r'(?i)("(?:access_token|refresh_token|id_token|authorization|api_key|secret|password|token)"\s*:\s*")([^"]*)(")'
)
_SECRET_AUTH_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")


def redact_body(text: str) -> str:
    text = redact_secrets(text)
    text = _SECRET_AUTH_RE.sub(lambda match: f"{match.group(1)} [redacted]", text)
    return _SECRET_JSON_RE.sub(lambda match: f"{match.group(1)}[redacted]{match.group(3)}", text)


def _header(headers: object, name: str) -> str:
    if headers is None:
        return ""
    try:
        value = headers.get(name)
    except Exception:
        return ""
    return str(value or "")


def _binary_type(content_type: str) -> bool:
    ctype = content_type.lower()
    return any(
        marker in ctype
        for marker in ("multipart/", "octet-stream", "image/", "audio/", "video/", "application/pdf", "application/zip")
    )


def preview_body(data: bytes | str | None, content_type: str = "") -> str:
    """Текст тела для лога. Файлы не разворачиваем, секреты вырезаем."""
    if data is None:
        return ""
    if isinstance(data, str):
        raw = data.encode("utf-8", "replace")
    else:
        raw = bytes(data)
    if not raw:
        return ""
    if _binary_type(content_type):
        label = content_type.split(";", 1)[0].strip() or "binary"
        return f"[{label}, {len(raw)} bytes]"
    text = raw.decode("utf-8", "replace")
    if "\x00" in text:
        label = content_type.split(";", 1)[0].strip() or "binary"
        return f"[{label}, {len(raw)} bytes]"
    text = redact_body(text)
    if len(text) > _BODY_LIMIT:
        return text[:_BODY_LIMIT] + "…"
    return text


def _request_preview(request: object) -> str:
    try:
        content_type = _header(getattr(request, "headers", None), "content-type")
        body = getattr(request, "content", None)
        if body is None:
            body = getattr(request, "body", None)
        if not isinstance(body, (bytes, bytearray, str)):
            return ""
        return preview_body(body, content_type)
    except Exception:
        return ""


def _response_preview_from_bytes(response: object, data: bytes | str | None) -> str:
    return preview_body(data, _header(getattr(response, "headers", None), "content-type"))


def _log_outbound(
    *,
    method: str,
    url: object,
    status_code: int | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
    client: str,
    request_body: str = "",
    response_body: str = "",
) -> None:
    target = sanitize_url(url)
    parts = urlsplit(target)
    fields: dict[str, Any] = {
        "event": "http.outbound",
        "direction": "outbound",
        "client": client,
        "method": method.upper(),
        "url": target,
        "host": parts.hostname,
        "path": parts.path or "/",
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if error:
        fields["error"] = error[:500]
    if request_body:
        fields["request_body"] = request_body
    if response_body:
        fields["response_body"] = response_body
    logger.info("Исходящий HTTP", extra=fields)


def _wrap_sync_send(original: Callable, client: str) -> Callable:
    @wraps(original)
    def send(self, request, *args, **kwargs):
        method = getattr(request, "method", None) or kwargs.get("method") or "?"
        url = getattr(request, "url", None) or request
        started = time.perf_counter()
        try:
            response = original(self, request, *args, **kwargs)
            status = getattr(response, "status_code", None)
            response_body = ""
            try:
                payload = getattr(response, "content", None)
                if not isinstance(payload, (bytes, bytearray, str)):
                    read = getattr(response, "read", None)
                    payload = read() if callable(read) else None
                response_body = _response_preview_from_bytes(response, payload)
            except Exception:
                response_body = ""
            _log_outbound(
                method=str(method),
                url=url,
                status_code=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                client=client,
                request_body=_request_preview(request),
                response_body=response_body,
            )
            return response
        except Exception as exc:
            _log_outbound(
                method=str(method),
                url=url,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error=str(exc),
                client=client,
                request_body=_request_preview(request),
            )
            raise

    return send


def _wrap_async_send(original: Callable, client: str) -> Callable:
    @wraps(original)
    async def send(self, request, *args, **kwargs):
        method = getattr(request, "method", None) or "?"
        url = getattr(request, "url", None) or request
        started = time.perf_counter()
        try:
            response = await original(self, request, *args, **kwargs)
            status = getattr(response, "status_code", None)
            response_body = ""
            try:
                aread = getattr(response, "aread", None)
                payload = await aread() if callable(aread) else getattr(response, "content", None)
                response_body = _response_preview_from_bytes(response, payload)
            except Exception:
                response_body = ""
            _log_outbound(
                method=str(method),
                url=url,
                status_code=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                client=client,
                request_body=_request_preview(request),
                response_body=response_body,
            )
            return response
        except Exception as exc:
            _log_outbound(
                method=str(method),
                url=url,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error=str(exc),
                client=client,
                request_body=_request_preview(request),
            )
            raise

    return send


def install_outbound_http_logging() -> None:
    """Один раз патчит httpx / httpx2 / requests — ловит и SDK (OpenAI, ЮKassa)."""
    global _HTTP_LOGGING_INSTALLED
    if _HTTP_LOGGING_INSTALLED:
        return
    _HTTP_LOGGING_INSTALLED = True

    try:
        import httpx

        httpx.Client.send = _wrap_sync_send(httpx.Client.send, "httpx")  # type: ignore[method-assign]
        httpx.AsyncClient.send = _wrap_async_send(httpx.AsyncClient.send, "httpx")  # type: ignore[method-assign]
    except Exception:
        logger.exception("Не удалось включить логирование httpx")

    try:
        import httpx2

        httpx2.Client.send = _wrap_sync_send(httpx2.Client.send, "httpx2")  # type: ignore[method-assign]
        if hasattr(httpx2, "AsyncClient"):
            httpx2.AsyncClient.send = _wrap_async_send(httpx2.AsyncClient.send, "httpx2")  # type: ignore[method-assign]
    except ImportError:
        pass
    except Exception:
        logger.exception("Не удалось включить логирование httpx2")

    try:
        import requests

        requests.Session.send = _wrap_sync_send(requests.Session.send, "requests")  # type: ignore[method-assign]
    except Exception:
        logger.exception("Не удалось включить логирование requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый входящий HTTP-запрос."""

    def __init__(self, app: ASGIApp, *, skip_paths: frozenset[str] | None = None) -> None:
        super().__init__(app)
        self.skip_paths = skip_paths or frozenset()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.skip_paths:
            return await call_next(request)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            logger.info(
                "Входящий HTTP",
                extra={
                    "event": "http.inbound",
                    "direction": "inbound",
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query or ""),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "client_ip": request.client.host if request.client else None,
                },
            )
