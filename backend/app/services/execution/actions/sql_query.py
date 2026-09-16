from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from urllib.parse import urlparse

import asyncpg

from core.config import settings
from core.user_errors import ERROR_SQL
from helper import apply_variable_assignments, render_template
from schemas.workflow import SqlQueryNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload

_QUERY_TIMEOUT_SECONDS = 30
_CONNECT_TIMEOUT_SECONDS = 10


def _normalize_dsn(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("postgresql+asyncpg://"):
        return "postgresql://" + text[len("postgresql+asyncpg://"):]
    if text.startswith("postgres://"):
        return "postgresql://" + text[len("postgres://"):]
    return text


def _endpoint(url: str) -> tuple[str, str, str]:
    parsed = urlparse(_normalize_dsn(url))
    host = (parsed.hostname or "").lower()
    port = str(parsed.port or 5432)
    database = (parsed.path or "").lstrip("/")
    return host, port, database


def _is_app_database(dsn: str) -> bool:
    try:
        return _endpoint(dsn) == _endpoint(settings.db_url)
    except Exception:
        return False


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


class SqlQueryAction(NodeAction):
    async def execute(self, node: SqlQueryNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        dsn = _normalize_dsn(render_template(node.dsn, payload, variables))
        query = render_template(node.query, payload, variables).strip()
        if not dsn:
            raise ValueError("Укажите строку подключения")
        if not query:
            raise ValueError("Укажите SQL-запрос")
        if _is_app_database(dsn):
            raise ValueError("Нельзя подключаться к служебной базе")
        parsed = urlparse(dsn)
        if parsed.scheme not in {"postgresql", "postgres"}:
            raise ValueError("Поддерживается только PostgreSQL")
        if not parsed.hostname:
            raise ValueError("В строке подключения нет хоста")
        connection = None
        try:
            connection = await asyncpg.connect(dsn=dsn, timeout=_CONNECT_TIMEOUT_SECONDS, command_timeout=_QUERY_TIMEOUT_SECONDS)
            try:
                await connection.execute("SET statement_timeout = 30000")
            except asyncpg.PostgresError:
                pass
            try:
                records = await connection.fetch(query)
                rows = [{str(key): _jsonable(value) for key, value in dict(record).items()} for record in records]
                output = {"engine": "postgresql", "rows": rows, "row_count": len(rows)}
            except asyncpg.InterfaceError:
                status = await connection.execute(query)
                output = {"engine": "postgresql", "rows": [], "row_count": 0, "status": status}
        except asyncpg.InvalidPasswordError:
            raise ValueError("Не удалось подключиться к базе данных") from None
        except (asyncpg.PostgresError, OSError, TimeoutError):
            raise ValueError(ERROR_SQL) from None
        finally:
            if connection is not None:
                await connection.close()
        apply_variable_assignments(node.assignments, output, context)
        return output
