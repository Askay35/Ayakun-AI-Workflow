from __future__ import annotations

from urllib.parse import quote

import httpx

from helper import apply_variable_assignments, render_template
from schemas.workflow import ExcelNode
from services.execution.actions.base import NodeAction
from services.execution.actions.google_sheets import _objects_from_values, _parse_values_json, _rows_from_values
from services.execution.actions.integration_http import call_api, response_json
from services.execution.context import incoming_payload

GRAPH_DRIVE = "https://graph.microsoft.com/v1.0/me/drive/root:"


def _segment(name: str) -> str:
    return quote("'" + name.replace("'", "''") + "'", safe="'")


class ExcelAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: ExcelNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})

        def text(value: str) -> str:
            return render_template(value or "", payload, variables).strip()

        token = text(node.access_token)
        file_path = text(node.file_path)
        if not token:
            raise ValueError("Excel: укажите токен Microsoft")
        if not file_path:
            raise ValueError("Excel: укажите путь к книге в OneDrive")
        if not file_path.startswith("/"):
            file_path = "/" + file_path
        workbook = f"{GRAPH_DRIVE}{quote(file_path, safe='/')}:/workbook"
        sheet = text(node.worksheet) or "Sheet1"
        cell_range = text(node.cell_range)
        sheet_url = f"{workbook}/worksheets({_segment(sheet)})"
        range_url = f"{sheet_url}/range(address={_segment(cell_range)})" if cell_range else f"{sheet_url}/usedRange"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if node.operation == "read":
            response = await call_api(self.client, "Excel", "GET", range_url, headers=headers)
        else:
            values = _rows_from_values(_parse_values_json(node.values_json, payload, variables))
            if not values:
                raise ValueError("Excel: нет строк для записи")
            if node.operation == "append":
                table = text(node.table)
                if not table:
                    raise ValueError("Excel: для добавления строк укажите имя таблицы")
                response = await call_api(
                    self.client, "Excel", "POST", f"{workbook}/tables({_segment(table)})/rows",
                    headers=headers, json={"values": values},
                )
            else:
                if not cell_range:
                    raise ValueError("Excel: для обновления укажите диапазон, например A2:C2")
                response = await call_api(
                    self.client, "Excel", "PATCH", range_url, headers=headers, json={"values": values},
                )
        body = response_json(response, "Excel")
        result = body if isinstance(body, dict) else {}
        values = result.get("values") if isinstance(result.get("values"), list) else []
        output: dict = {
            "operation": node.operation,
            "file_path": file_path,
            "worksheet": sheet,
            "range": result.get("address") or cell_range,
            "values": values,
            "rows": _objects_from_values(values) if node.operation == "read" else [],
        }
        if node.operation == "read":
            output["row_count"] = len(output["rows"])
        apply_variable_assignments(node.assignments, output, context)
        return output
