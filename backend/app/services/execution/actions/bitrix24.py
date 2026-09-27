from __future__ import annotations

import json

import httpx

from helper import apply_variable_assignments, render_template
from schemas.workflow import Bitrix24Node
from services.execution.actions.base import NodeAction
from services.execution.actions.integration_http import call_api, require_https, response_json
from services.execution.context import incoming_payload

ENTITY_TYPE_ID = {"lead": 1, "deal": 2, "contact": 3, "company": 4}


def _parse_json_field(raw: str, payload: object, variables: dict, default: object) -> object:
    text = (raw or "").strip()
    if not text:
        return default
    rendered = render_template(text, payload, variables)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Битрикс24: некорректный JSON — {exc.msg}") from exc


class Bitrix24Action(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: Bitrix24Node, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})

        def text(value: str) -> str:
            return render_template(value or "", payload, variables).strip()

        webhook = require_https(text(node.webhook_url), "Битрикс24")
        entity_type_id = ENTITY_TYPE_ID[node.entity]
        item_id = text(node.item_id)
        if node.operation in {"update", "get", "delete"} and not item_id:
            raise ValueError("Битрикс24: укажите ID элемента")

        default_fields = payload if isinstance(payload, dict) else {}
        if node.operation == "create":
            fields = _parse_json_field(node.fields_json, payload, variables, default_fields)
            if not isinstance(fields, dict) or not fields:
                raise ValueError("Битрикс24: укажите поля элемента (JSON)")
            method, body = "crm.item.add", {"entityTypeId": entity_type_id, "fields": fields}
        elif node.operation == "update":
            fields = _parse_json_field(node.fields_json, payload, variables, default_fields)
            if not isinstance(fields, dict) or not fields:
                raise ValueError("Битрикс24: укажите поля для обновления (JSON)")
            method, body = "crm.item.update", {"entityTypeId": entity_type_id, "id": item_id, "fields": fields}
        elif node.operation == "get":
            method, body = "crm.item.get", {"entityTypeId": entity_type_id, "id": item_id}
        elif node.operation == "delete":
            method, body = "crm.item.delete", {"entityTypeId": entity_type_id, "id": item_id}
        else:
            filter_ = _parse_json_field(node.filter_json, payload, variables, {})
            if not isinstance(filter_, dict):
                raise ValueError("Битрикс24: фильтр должен быть JSON-объектом")
            method, body = "crm.item.list", {"entityTypeId": entity_type_id, "filter": filter_, "select": ["*"]}

        response = await call_api(self.client, "Битрикс24", "POST", f"{webhook}/{method}.json", json=body)
        result = response_json(response, "Битрикс24")
        data = result.get("result") if isinstance(result, dict) else None

        if node.operation == "list":
            raw_items = data.get("items") if isinstance(data, dict) else data
            items = raw_items if isinstance(raw_items, list) else []
            output: dict = {"operation": node.operation, "entity": node.entity, "items": items, "count": len(items)}
        elif node.operation == "delete":
            output = {"operation": node.operation, "entity": node.entity, "id": item_id, "deleted": bool(data)}
        else:
            item = data.get("item") if isinstance(data, dict) else data
            output = {"operation": node.operation, "entity": node.entity, "item": item if isinstance(item, dict) else {}}

        apply_variable_assignments(node.assignments, output, context)
        return output
