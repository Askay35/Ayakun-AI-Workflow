from helper import apply_variable_assignments
from schemas.workflow import WebhookNode
from services.execution.actions.base import NodeAction

_INTERNAL_KEYS = {"_solo", "_solo_node_id", "_solo_node_type"}


class WebhookAction(NodeAction):
    async def execute(self, node: WebhookNode, context: dict) -> dict:
        raw = context.get("input") or {}
        payload = {key: value for key, value in dict(raw).items() if key not in _INTERNAL_KEYS} if isinstance(raw, dict) else {}
        if any(key in payload for key in ("body", "headers", "query", "method")):
            headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
            query = payload.get("query") if isinstance(payload.get("query"), dict) else {}
            output = {
                "method": str(payload.get("method") or "POST"),
                "headers": headers,
                "query": query,
                "body": payload.get("body", {}),
            }
        else:
            output = {"method": "POST", "headers": {}, "query": {}, "body": payload}
        apply_variable_assignments(getattr(node, "assignments", None), output, context)
        return output
