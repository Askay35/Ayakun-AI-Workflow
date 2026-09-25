from __future__ import annotations

import httpx

from helper import render_template
from schemas.workflow import SlackNode
from services.execution.actions.base import NodeAction
from services.execution.actions.integration_http import call_api, response_json
from services.execution.context import incoming_payload, parent_output_texts

SLACK_TEXT_LIMIT = 39_000
SLACK_WEBHOOK_PREFIX = "https://hooks.slack.com/"


class SlackAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: SlackNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        if (node.message or "").strip():
            text = render_template(node.message, payload, variables)
        else:
            texts = parent_output_texts(node, context)
            text = texts[0] if texts else ""
        if not text.strip():
            return {"sent": False, "text": ""}
        if len(text) > SLACK_TEXT_LIMIT:
            text = text[: SLACK_TEXT_LIMIT - 1] + "…"
        webhook_url = render_template(node.webhook_url or "", payload, variables).strip()
        if webhook_url:
            if not webhook_url.startswith(SLACK_WEBHOOK_PREFIX):
                raise ValueError("Slack: адрес вебхука должен начинаться с hooks.slack.com")
            await call_api(self.client, "Slack", "POST", webhook_url, json={"text": text})
            return {"sent": True, "channel": "webhook", "text": text}
        token = render_template(node.bot_token or "", payload, variables).strip()
        channel = render_template(node.channel or "", payload, variables).strip()
        if not token or not channel:
            raise ValueError("Slack: укажите вебхук или токен бота и канал")
        response = await call_api(
            self.client,
            "Slack",
            "POST",
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text},
        )
        body = response_json(response, "Slack")
        if not isinstance(body, dict) or not body.get("ok"):
            error = body.get("error") if isinstance(body, dict) else None
            raise ValueError(f"Slack: сообщение не отправлено ({error or 'неизвестная ошибка'})")
        return {"sent": True, "channel": body.get("channel") or channel, "ts": body.get("ts"), "text": text}
