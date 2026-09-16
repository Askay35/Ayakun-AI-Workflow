from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from core.config import settings
from core.user_errors import ERROR_GOOGLE_SHEETS
from helper import apply_variable_assignments, render_template
from schemas.workflow import GoogleSheetsNode
from services.execution.actions.base import NodeAction
from services.execution.actions.google_auth import google_service_account_token, rendered_secret
from services.execution.context import incoming_payload

_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def _rows_from_values(raw: object) -> list[list[object]]:
    data = raw
    if isinstance(data, dict):
        if isinstance(data.get("values"), list):
            data = data["values"]
        elif isinstance(data.get("rows"), list):
            data = data["rows"]
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("Значения строк должны быть JSON-массивом")
    if not data:
        return []
    if isinstance(data[0], dict):
        keys = list(data[0].keys())
        return [[item.get(key, "") if isinstance(item, dict) else "" for key in keys] for item in data]
    if isinstance(data[0], list):
        return [list(item) for item in data]
    return [[item] for item in data]


def _objects_from_values(values: list) -> list[dict[str, object]]:
    if not values:
        return []
    header_row = values[0] if isinstance(values[0], list) else [values[0]]
    headers = [str(item).strip() or f"col_{index + 1}" for index, item in enumerate(header_row)]
    rows: list[dict[str, object]] = []
    for raw in values[1:]:
        cells = list(raw) if isinstance(raw, list) else [raw]
        row = {headers[index]: (cells[index] if index < len(cells) else "") for index in range(len(headers))}
        rows.append(row)
    return rows


def _parse_values_json(raw: str, payload: object, variables: dict) -> object:
    text = (raw or "").strip()
    if not text:
        return payload
    rendered = render_template(text, payload, variables)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Значения строк содержат некорректный JSON: {exc.msg}") from exc


class GoogleSheetsAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    def _auth(self, node: GoogleSheetsNode, payload: object, variables: dict) -> tuple[dict[str, str], dict[str, str]]:
        token = rendered_secret(node.access_token, payload, variables)
        if not token and (node.service_account_json or "").strip():
            account = rendered_secret(node.service_account_json, payload, variables) or node.service_account_json
            token = google_service_account_token(account, [_SHEETS_SCOPE])
        headers = {"Accept": "application/json"}
        params: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            key = rendered_secret(node.api_key, payload, variables)
            if key:
                params["key"] = key
        return headers, params

    def _url(self, spreadsheet_id: str, sheet_range: str, suffix: str = "") -> str:
        encoded_range = quote(sheet_range, safe="")
        path = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{encoded_range}"
        return path + suffix

    async def execute(self, node: GoogleSheetsNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        spreadsheet_id = render_template(node.spreadsheet_id, payload, variables).strip()
        sheet_range = render_template(node.sheet_range or "Sheet1!A1:Z", payload, variables).strip()
        if not spreadsheet_id:
            raise ValueError("Укажите идентификатор таблицы")
        if not sheet_range:
            raise ValueError("Укажите диапазон листа")
        headers, params = self._auth(node, payload, variables)
        if "Authorization" not in headers and "key" not in params:
            raise ValueError("Укажите токен Google, API-ключ или JSON сервисного аккаунта")
        try:
            if node.operation == "read":
                response = await self.client.get(
                    self._url(spreadsheet_id, sheet_range),
                    headers=headers,
                    params=params,
                    timeout=settings.provider_timeout_seconds,
                )
            else:
                values = _rows_from_values(_parse_values_json(node.values_json, payload, variables))
                body = {"values": values}
                write_params = {**params, "valueInputOption": "USER_ENTERED"}
                if node.operation == "append":
                    write_params["insertDataOption"] = "INSERT_ROWS"
                    response = await self.client.post(
                        self._url(spreadsheet_id, sheet_range, ":append"),
                        headers={**headers, "Content-Type": "application/json"},
                        params=write_params,
                        json=body,
                        timeout=settings.provider_timeout_seconds,
                    )
                else:
                    response = await self.client.put(
                        self._url(spreadsheet_id, sheet_range),
                        headers={**headers, "Content-Type": "application/json"},
                        params=write_params,
                        json=body,
                        timeout=settings.provider_timeout_seconds,
                    )
        except httpx.RequestError:
            raise ValueError(ERROR_GOOGLE_SHEETS) from None
        if response.is_error:
            if response.status_code in {401, 403}:
                raise ValueError("Не удалось авторизоваться в Google Таблицах")
            raise ValueError(ERROR_GOOGLE_SHEETS)
        try:
            result = response.json()
        except json.JSONDecodeError:
            raise ValueError(ERROR_GOOGLE_SHEETS) from None
        if not isinstance(result, dict):
            result = {"data": result}
        values = result.get("values") if isinstance(result.get("values"), list) else []
        output: dict[str, Any] = {
            "spreadsheet_id": spreadsheet_id,
            "range": result.get("updatedRange") or result.get("tableRange") or result.get("range") or sheet_range,
            "operation": node.operation,
            "values": values,
            "rows": _objects_from_values(values) if node.operation == "read" else [],
            "updated_rows": result.get("updates", {}).get("updatedRows") if isinstance(result.get("updates"), dict) else result.get("updatedRows"),
            "updated_cells": result.get("updates", {}).get("updatedCells") if isinstance(result.get("updates"), dict) else result.get("updatedCells"),
        }
        if node.operation == "read":
            output["row_count"] = len(output["rows"])
        apply_variable_assignments(node.assignments, output, context)
        return output
