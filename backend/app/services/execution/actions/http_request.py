import json

import httpx

from core.config import settings
from helper import apply_variable_assignments, form_request_body, json_root_from_output
from schemas.workflow import HttpRequestNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_records


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
        method = str(request_data.get("method") or "GET").upper()
        url = request_data.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("В данных запроса не указан url")
        headers = request_data.get("headers") or {}
        if headers and not isinstance(headers, dict):
            raise ValueError("headers в данных запроса должны быть JSON-объектом")
        body = request_data.get("body")
        kwargs: dict = {
            "method": method,
            "url": url.strip(),
            "headers": headers,
            "timeout": settings.provider_timeout_seconds,
        }
        if body is not None:
            kwargs["json"] = body
        response = await self.client.request(**kwargs)
        if response.is_error:
            snippet = (response.text or "")[:500]
            raise ValueError(f"HTTP {response.status_code}: {snippet or 'ошибка запроса'}")
        if not response.content:
            empty = {"status": response.status_code}
            apply_variable_assignments(node.assignments, empty, context)
            return empty
        try:
            payload = response.json()
        except json.JSONDecodeError:
            text_payload = {"status": response.status_code, "text": response.text}
            apply_variable_assignments(node.assignments, text_payload, context)
            return text_payload
        if isinstance(payload, (dict, list)):
            apply_variable_assignments(node.assignments, payload, context)
            return payload
        wrapped = {"data": payload}
        apply_variable_assignments(node.assignments, wrapped, context)
        return wrapped
