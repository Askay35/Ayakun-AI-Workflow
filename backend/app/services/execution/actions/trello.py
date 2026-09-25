from __future__ import annotations

from urllib.parse import quote

import httpx

from helper import apply_variable_assignments, render_template
from schemas.workflow import TrelloNode
from services.execution.actions.base import NodeAction
from services.execution.actions.integration_http import call_api, response_json
from services.execution.context import incoming_payload

TRELLO_API = "https://api.trello.com/1"


def _card(item: object) -> dict:
    if not isinstance(item, dict):
        return {}
    labels = item.get("labels") if isinstance(item.get("labels"), list) else []
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "description": item.get("desc") or "",
        "url": item.get("shortUrl") or item.get("url"),
        "list_id": item.get("idList"),
        "due": item.get("due"),
        "labels": [label.get("name") for label in labels if isinstance(label, dict) and label.get("name")],
    }


class TrelloAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: TrelloNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})

        def text(value: str) -> str:
            return render_template(value or "", payload, variables).strip()

        key, token = text(node.api_key), text(node.token)
        if not key or not token:
            raise ValueError("Trello: укажите API-ключ и токен")
        auth = {"key": key, "token": token}
        list_id, card_id = text(node.list_id), text(node.card_id)
        if node.operation == "create_card":
            name = text(node.name)
            if not list_id or not name:
                raise ValueError("Trello: укажите список и название карточки")
            response = await call_api(
                self.client, "Trello", "POST", f"{TRELLO_API}/cards",
                params={**auth, "idList": list_id, "name": name, "desc": text(node.description)},
            )
            output: dict = {"operation": node.operation, "card": _card(response_json(response, "Trello"))}
        elif node.operation == "list_cards":
            if not list_id:
                raise ValueError("Trello: укажите список")
            response = await call_api(
                self.client, "Trello", "GET", f"{TRELLO_API}/lists/{quote(list_id, safe='')}/cards", params=auth,
            )
            body = response_json(response, "Trello")
            cards = [_card(item) for item in body] if isinstance(body, list) else []
            output = {"operation": node.operation, "cards": cards, "count": len(cards)}
        elif node.operation == "move_card":
            if not card_id or not list_id:
                raise ValueError("Trello: укажите карточку и список, куда её перенести")
            response = await call_api(
                self.client, "Trello", "PUT", f"{TRELLO_API}/cards/{quote(card_id, safe='')}",
                params={**auth, "idList": list_id},
            )
            output = {"operation": node.operation, "card": _card(response_json(response, "Trello"))}
        else:
            comment = text(node.description)
            if not card_id or not comment:
                raise ValueError("Trello: укажите карточку и текст комментария")
            response = await call_api(
                self.client, "Trello", "POST", f"{TRELLO_API}/cards/{quote(card_id, safe='')}/actions/comments",
                params={**auth, "text": comment},
            )
            body = response_json(response, "Trello")
            output = {
                "operation": node.operation,
                "card_id": card_id,
                "comment_id": body.get("id") if isinstance(body, dict) else None,
                "text": comment,
            }
        apply_variable_assignments(node.assignments, output, context)
        return output
