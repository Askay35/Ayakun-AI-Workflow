from helper import escape_telegram_markdown, expression_root, json_root_from_output, render_telegram_message, render_template
from schemas.workflow import TelegramSendNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_output_texts, parent_records
from services.providers import TelegramNotificationProvider

TELEGRAM_TEXT_LIMIT = 4096


class TelegramSendAction(NodeAction):
    def __init__(self, notifications: TelegramNotificationProvider):
        self.notifications = notifications

    async def execute(self, node: TelegramSendNode, context: dict) -> dict:
        records = parent_records(node, context)
        if len(records) > 1:
            raise ValueError("Telegram может иметь только одну входящую связь")
        if records:
            payload = expression_root(records[0].get("output"))
        else:
            payload = json_root_from_output(context.get("input") or {})
        variables = context.setdefault("variables", {})
        raw_chat = str(node.chat_id or "").strip()
        if raw_chat:
            chat_id = render_template(raw_chat, payload, variables).strip()
        else:
            chat_id = str(context.get("input", {}).get("chat_id") or "").strip()
        template = (node.message or "").strip()
        if template:
            message = render_telegram_message(template, payload, variables)
        else:
            texts = parent_output_texts(node, context)
            raw = texts[0] if texts else ""
            message = escape_telegram_markdown(raw)
        if not message:
            return {"sent": False, "text": ""}
        if not chat_id:
            raise ValueError("telegram_send требует chat_id")
        if len(message) > TELEGRAM_TEXT_LIMIT:
            message = message[: TELEGRAM_TEXT_LIMIT - 1] + "…"
        bot_token = (node.bot_token or "").strip() or None
        await self.notifications.send(str(chat_id), message, bot_token=bot_token)
        return {"sent": True, "text": message}
