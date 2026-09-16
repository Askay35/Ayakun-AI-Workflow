import json
import logging

import httpx

from core.config import settings
from core.user_errors import ERROR_HTTP
from helper import apply_variable_assignments, form_request_body, json_root_from_output
from schemas.workflow import HttpRequestNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_records

logger = logging.getLogger(__name__)

_NO_BODY_METHODS = {"GET", "HEAD", "OPTIONS"}
_PLACEHOLDER_AUTH = {"bearer ...", "bearer", "..."}


def _header_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _request_headers(raw: object) -> dict[str, str]:
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("headers в данных запроса должны быть JSON-объектом")
    headers: dict[str, str] = {}
    for key, value in raw.items():
        text = _header_value(value)
        if text is None:
            continue
        name = str(key)
        if name.lower() == "authorization" and text.strip().lower() in _PLACEHOLDER_AUTH:
            continue
        headers[name] = text
    return headers


def _request_kwargs(request_data: dict) -> dict:
    method = str(request_data.get("method") or "GET").upper()
    url = request_data.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("В данных запроса не указан url")
    kwargs: dict = {
        "method": method,
        "url": url.strip(),
        "headers": _request_headers(request_data.get("headers")),
        "timeout": settings.provider_timeout_seconds,
        "follow_redirects": True,
    }
    query = request_data.get("params")
    if query is None:
        query = request_data.get("query")
    if isinstance(query, dict) and query:
        kwargs["params"] = query
    body = request_data.get("body")
    if body is not None and method not in _NO_BODY_METHODS:
        if isinstance(body, (dict, list)):
            kwargs["json"] = body
        elif isinstance(body, (bytes, bytearray)):
            kwargs["content"] = bytes(body)
        else:
            kwargs["content"] = str(body).encode()
    return kwargs


def _payload_from_response(response: httpx.Response) -> dict | list:
    if not response.content:
        return {"status": response.status_code}
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return {"status": response.status_code, "text": response.text}
    if isinstance(payload, (dict, list)):
        return payload
    return {"data": payload}


class HttpRequestAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: HttpRequestNode, context: dict) -> dict | list:
        records = parent_records(node, context)
        if len(records) > 1:
            raise ValueError("HTTP Request может иметь только одну входящую связь")
        parent_output = records[0].get("output") if records else None
        request_data = form_request_body(
            node.request_json,
            json_root_from_output(parent_output) if parent_output is not None else {},
            context.setdefault("variables", {}),
        )
        kwargs = _request_kwargs(request_data)
        try:
            response = await self.client.request(**kwargs)
        except httpx.RequestError:
            logger.warning("HTTP request node failed", extra={"event": "http_request.failed"})
            raise ValueError(ERROR_HTTP) from None
        if response.is_error:
            logger.warning(
                "HTTP request node rejected",
                extra={"event": "http_request.failed", "status_code": response.status_code},
            )
        payload = _payload_from_response(response)
        apply_variable_assignments(node.assignments, payload, context)
        return payload
