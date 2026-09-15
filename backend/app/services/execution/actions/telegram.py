from helper import expression_root, render_template
from schemas.workflow import TelegramSendNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_output_texts, parent_records
from services.providers import TelegramNotificationProvider

TELEGRAM_TEXT_LIMIT = 4096


class TelegramSendAction(NodeAction):
    def __init__(self, notifications: TelegramNotificationProvider):
        self.notifications = notifications

    async def execute(self, node: TelegramSendNode, context: dict) -> dict:
        chat_id = node.chat_id or context.get("input", {}).get("chat_id")
        records = parent_records(node, context)
        if len(records) > 1:
            raise ValueError("Telegram может иметь только одну входящую связь")
        template = (node.message or "").strip()
        if template:
            parent_output = records[0].get("output") if records else None
            message = render_template(
                template,
                expression_root(parent_output),
                context.setdefault("variables", {}),
            )
        else:
            texts = parent_output_texts(node, context)
            message = texts[0] if texts else ""
        if not message:
            return {"sent": False, "text": ""}
        if not chat_id:
            raise ValueError("telegram_send требует chat_id")
        if len(message) > TELEGRAM_TEXT_LIMIT:
            message = message[: TELEGRAM_TEXT_LIMIT - 1] + "…"
        await self.notifications.send(str(chat_id), message)
        return {"sent": True, "text": message}
