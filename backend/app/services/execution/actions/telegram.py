import os

import httpx

from helper import markdown_to_telegram, expression_root, json_root_from_output, render_telegram_message, render_template
from schemas.workflow import TelegramSendNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_output_texts, parent_records
from services.media_files import file_output, load_binary
from services.providers import TelegramNotificationProvider

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024


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
        parent = records[0].get("output") if records else None
        incoming = file_output(parent)
        template = (node.message or "").strip()
        if template:
            message = render_telegram_message(template, payload, variables)
        elif incoming is not None:
            message = ""
        else:
            texts = parent_output_texts(node, context)
            raw = texts[0] if texts else ""
            message = markdown_to_telegram(raw)
        if not message and incoming is None:
            return {"sent": False, "text": ""}
        if not chat_id:
            raise ValueError("telegram_send требует chat_id")
        if len(message) > TELEGRAM_TEXT_LIMIT:
            message = message[: TELEGRAM_TEXT_LIMIT - 1] + "…"
        bot_token = (node.bot_token or "").strip() or None
        if incoming is not None:
            data, mime, filename = await _load_file(incoming)
            safe_name = os.path.basename(filename) or "file"
            caption = message if message and len(message) <= TELEGRAM_CAPTION_LIMIT else ""
            await self.notifications.send_file(str(chat_id), data, safe_name, mime, caption or None, bot_token=bot_token)
            if message and not caption:
                await self.notifications.send(str(chat_id), message, bot_token=bot_token)
            return {"sent": True, "text": message, "file": safe_name}
        await self.notifications.send(str(chat_id), message, bot_token=bot_token)
        return {"sent": True, "text": message}


async def _load_file(payload: dict) -> tuple[bytes, str, str]:
    async with httpx.AsyncClient(timeout=60) as client:
        return await load_binary(payload, client)
