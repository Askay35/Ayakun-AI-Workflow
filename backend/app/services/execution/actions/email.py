from __future__ import annotations

from fastapi import HTTPException

from core.user_errors import ERROR_EMAIL
from helper import apply_variable_assignments, render_template
from schemas.workflow import EmailNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload
from services.providers import EmailProvider, SMTPEmailProvider


def _split_recipients(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").replace(";", ",").split(",") if part.strip()]


class EmailAction(NodeAction):
    def __init__(self, mail: EmailProvider | None = None):
        self.mail = mail or SMTPEmailProvider()

    async def execute(self, node: EmailNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        to = render_template(node.to, payload, variables).strip()
        subject = render_template(node.subject, payload, variables)
        body = render_template(node.body, payload, variables)
        recipients = _split_recipients(to)
        if not recipients:
            raise ValueError("Укажите получателя письма")
        try:
            await self.mail.send(", ".join(recipients), subject, body)
        except HTTPException:
            raise ValueError("Почта не настроена") from None
        except Exception:
            raise ValueError(ERROR_EMAIL) from None
        output = {
            "sent": True,
            "to": recipients,
            "subject": subject,
        }
        apply_variable_assignments(node.assignments, output, context)
        return output
