from __future__ import annotations

import asyncio
import datetime
import uuid
from decimal import Decimal
from urllib.parse import unquote, urlparse

import asyncpg

from core.config import settings
from core.user_errors import ERROR_SQL
from helper import apply_variable_assignments, render_template
from schemas.workflow import SqlQueryNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload

_QUERY_TIMEOUT_SECONDS = 30
_CONNECT_TIMEOUT_SECONDS = 10
_ENGINE_SCHEMES = {
    "postgresql": {"postgresql", "postgres"},
    "mysql": {"mysql", "mariadb"},
    "clickhouse": {"clickhouse", "clickhouses"},
}
_SCHEME_PREFIX = {
    "postgresql": "postgresql://",
    "mysql": "mysql://",
    "clickhouse": "clickhouse://",
}


def _normalize_dsn(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("postgresql+asyncpg://"):
        return "postgresql://" + text[len("postgresql+asyncpg://"):]
    if text.startswith("postgres://"):
        return "postgresql://" + text[len("postgres://"):]
    if text.startswith("mysql+aiomysql://"):
        return "mysql://" + text[len("mysql+aiomysql://"):]
    if text.startswith("mysql+pymysql://"):
        return "mysql://" + text[len("mysql+pymysql://"):]
    if text.startswith("mariadb://"):
        return "mysql://" + text[len("mariadb://"):]
    if text.startswith("clickhouse+https://"):
        return "clickhouses://" + text[len("clickhouse+https://"):]
    if text.startswith("clickhouse+http://"):
        return "clickhouse://" + text[len("clickhouse+http://"):]
    if text.startswith("clickhouse+native://"):
        return "clickhouse://" + text[len("clickhouse+native://"):]
    return text


def _with_scheme(dsn: str, engine: str) -> str:
    if "://" in dsn:
        return dsn
    prefix = _SCHEME_PREFIX.get(engine, "postgresql://")
    return prefix + dsn


def _engine_from_dsn(dsn: str, requested: str) -> str:
    dsn = _normalize_dsn(dsn)
    scheme = (urlparse(dsn).scheme or "").lower()
    for engine, schemes in _ENGINE_SCHEMES.items():
        if scheme in schemes:
            return engine
    if scheme in {"http", "https"} and requested == "clickhouse":
        return "clickhouse"
    known = {item for schemes in _ENGINE_SCHEMES.values() for item in schemes}
    if scheme and scheme not in known:
        raise ValueError("Поддерживаются PostgreSQL, MySQL и ClickHouse")
    if requested in _ENGINE_SCHEMES:
        return requested
    raise ValueError("Поддерживаются PostgreSQL, MySQL и ClickHouse")


def _endpoint(url: str, default_port: int = 5432) -> tuple[str, str, str]:
    parsed = urlparse(_normalize_dsn(url))
    host = (parsed.hostname or "").lower()
    port = str(parsed.port or default_port)
    database = (parsed.path or "").lstrip("/")
    return host, port, database


def _is_app_database(dsn: str) -> bool:
    try:
        if _engine_from_dsn(dsn, "postgresql") != "postgresql":
            return False
        return _endpoint(dsn) == _endpoint(settings.db_url)
    except Exception:
        return False


def _credentials(parsed) -> tuple[str, str, str]:
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = unquote((parsed.path or "").lstrip("/").split("/")[0])
    return user, password, database


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


async def _postgres(dsn: str, query: str) -> dict:
    connection = None
    try:
        connection = await asyncpg.connect(
            dsn=dsn,
            timeout=_CONNECT_TIMEOUT_SECONDS,
            command_timeout=_QUERY_TIMEOUT_SECONDS,
        )
        try:
            await connection.execute("SET statement_timeout = 30000")
        except asyncpg.PostgresError:
            pass
        try:
            records = await connection.fetch(query)
            rows = [{str(key): _jsonable(value) for key, value in dict(record).items()} for record in records]
            return {"engine": "postgresql", "rows": rows, "row_count": len(rows)}
        except asyncpg.InterfaceError:
            status = await connection.execute(query)
            return {"engine": "postgresql", "rows": [], "row_count": 0, "status": status}
    except asyncpg.InvalidPasswordError:
        raise ValueError("Не удалось подключиться к базе данных") from None
    except (asyncpg.PostgresError, OSError, TimeoutError):
        raise ValueError(ERROR_SQL) from None
    finally:
        if connection is not None:
            await connection.close()


async def _mysql(dsn: str, query: str) -> dict:
    try:
        import aiomysql
        import pymysql
    except ImportError:
        raise ValueError(ERROR_SQL) from None
    parsed = urlparse(dsn)
    if not parsed.hostname:
        raise ValueError("В строке подключения нет хоста")
    user, password, database = _credentials(parsed)
    connection = None
    try:
        connection = await aiomysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=user,
            password=password,
            db=database or None,
            charset="utf8mb4",
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            autocommit=True,
        )
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await asyncio.wait_for(cursor.execute(query), timeout=_QUERY_TIMEOUT_SECONDS)
            if cursor.description:
                records = await cursor.fetchall()
                rows = [{str(key): _jsonable(value) for key, value in dict(record).items()} for record in records]
                return {"engine": "mysql", "rows": rows, "row_count": len(rows)}
            return {"engine": "mysql", "rows": [], "row_count": cursor.rowcount or 0}
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else None
        if code in {1044, 1045, 2003, 2005}:
            raise ValueError("Не удалось подключиться к базе данных") from None
        raise ValueError(ERROR_SQL) from None
    except pymysql.err.Error:
        raise ValueError(ERROR_SQL) from None
    except (OSError, TimeoutError, asyncio.TimeoutError):
        raise ValueError(ERROR_SQL) from None
    finally:
        if connection is not None:
            connection.close()
            await connection.ensure_closed()


def _clickhouse(dsn: str, query: str) -> dict:
    try:
        import clickhouse_connect
        from clickhouse_connect.driver.exceptions import ClickHouseError
    except ImportError:
        raise ValueError(ERROR_SQL) from None
    parsed = urlparse(dsn)
    if not parsed.hostname:
        raise ValueError("В строке подключения нет хоста")
    user, password, database = _credentials(parsed)
    secure = parsed.scheme in {"clickhouses", "https"}
    client = None
    try:
        client = clickhouse_connect.get_client(
            host=parsed.hostname,
            port=parsed.port or (8443 if secure else 8123),
            username=user or "default",
            password=password,
            database=database or "default",
            secure=secure,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            send_receive_timeout=_QUERY_TIMEOUT_SECONDS,
        )
        result = client.query(query)
        rows = [
            {str(name): _jsonable(value) for name, value in zip(result.column_names, row, strict=False)}
            for row in result.result_rows
        ]
        return {"engine": "clickhouse", "rows": rows, "row_count": len(rows)}
    except (ClickHouseError, OSError, TimeoutError):
        raise ValueError(ERROR_SQL) from None
    finally:
        if client is not None:
            client.close()


class SqlQueryAction(NodeAction):
    async def execute(self, node: SqlQueryNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        dsn = _normalize_dsn(_with_scheme(render_template(node.dsn, payload, variables), node.engine))
        query = render_template(node.query, payload, variables).strip()
        if not dsn:
            raise ValueError("Укажите строку подключения")
        if not query:
            raise ValueError("Укажите SQL-запрос")
        engine = _engine_from_dsn(dsn, node.engine)
        if engine == "postgresql" and _is_app_database(dsn):
            raise ValueError("Нельзя подключаться к служебной базе")
        parsed = urlparse(dsn)
        if not parsed.hostname:
            raise ValueError("В строке подключения нет хоста")
        if engine == "postgresql":
            output = await _postgres(dsn, query)
        elif engine == "mysql":
            output = await _mysql(dsn, query)
        else:
            output = await asyncio.to_thread(_clickhouse, dsn, query)
        apply_variable_assignments(node.assignments, output, context)
        return output
