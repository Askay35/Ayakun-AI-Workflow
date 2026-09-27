from __future__ import annotations

import httpx
from fastapi import HTTPException

from core.user_errors import ERROR_EMAIL
from helper import apply_variable_assignments, render_template
from schemas.workflow import EmailNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload, parent_records
from services.media_files import file_output, load_binary
from services.providers import EmailAttachment, EmailProvider, SMTPEmailProvider


def _split_recipients(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").replace(";", ",").split(",") if part.strip()]


class EmailAction(NodeAction):
    def __init__(self, mail: EmailProvider | None = None, client: httpx.AsyncClient | None = None):
        self.mail = mail or SMTPEmailProvider()
        self.client = client

    async def execute(self, node: EmailNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        to = render_template(node.to, payload, variables).strip()
        subject = render_template(node.subject, payload, variables)
        body = render_template(node.body, payload, variables)
        recipients = _split_recipients(to)
        if not recipients:
            raise ValueError("Укажите получателя письма")
        attachments = await self._attachments(node, context)
        try:
            if attachments:
                await self.mail.send(", ".join(recipients), subject, body, attachments=attachments)
            else:
                await self.mail.send(", ".join(recipients), subject, body)
        except HTTPException:
            raise ValueError("Почта не настроена") from None
        except Exception:
            raise ValueError(ERROR_EMAIL) from None
        output = {
            "sent": True,
            "to": recipients,
            "subject": subject,
            "attached": bool(attachments),
        }
        apply_variable_assignments(node.assignments, output, context)
        return output

    async def _attachments(self, node: EmailNode, context: dict) -> list[EmailAttachment]:
        if not node.attach_file:
            return []
        records = parent_records(node, context)
        parent = records[0].get("output") if len(records) == 1 else None
        incoming = file_output(parent)
        if incoming is None:
            raise ValueError("Email: подключённый узел не вернул файл для вложения")
        client = self.client
        if client is not None:
            data, mime, filename = await load_binary(incoming, client)
        else:
            async with httpx.AsyncClient(timeout=60) as fallback:
                data, mime, filename = await load_binary(incoming, fallback)
        return [(data, filename, mime)]
