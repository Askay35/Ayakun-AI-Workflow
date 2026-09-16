from __future__ import annotations

import asyncio
import base64
import json
import smtplib
from email.message import EmailMessage

import httpx

from core.config import settings
from core.user_errors import ERROR_GMAIL
from helper import apply_variable_assignments, render_template
from schemas.workflow import GmailNode
from services.execution.actions.base import NodeAction
from services.execution.actions.google_auth import rendered_secret
from services.execution.context import incoming_payload

_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"


def _split_recipients(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").replace(";", ",").split(",") if part.strip()]


def _header_value(headers: list, name: str) -> str:
    needle = name.lower()
    for item in headers:
        if isinstance(item, dict) and str(item.get("name") or "").lower() == needle:
            return str(item.get("value") or "")
    return ""


def _raw_message(from_email: str, to: str, subject: str, body: str) -> str:
    message = EmailMessage()
    if from_email:
        message["From"] = from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body or "")
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return encoded.rstrip("=")


class GmailAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: GmailNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        if node.operation == "list":
            output = await self._list(node, payload, variables)
        else:
            output = await self._send(node, payload, variables)
        apply_variable_assignments(node.assignments, output, context)
        return output

    async def _send(self, node: GmailNode, payload: object, variables: dict) -> dict:
        to = render_template(node.to, payload, variables).strip()
        subject = render_template(node.subject, payload, variables)
        body = render_template(node.body, payload, variables)
        from_email = render_template(node.from_email, payload, variables).strip()
        recipients = _split_recipients(to)
        if not recipients:
            raise ValueError("Укажите получателя письма")
        if node.auth_mode == "oauth":
            token = rendered_secret(node.access_token, payload, variables)
            if not token:
                raise ValueError("Укажите OAuth-токен Gmail")
            try:
                response = await self.client.post(
                    _GMAIL_SEND_URL,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"raw": _raw_message(from_email, ", ".join(recipients), subject, body)},
                    timeout=settings.provider_timeout_seconds,
                )
            except httpx.RequestError:
                raise ValueError(ERROR_GMAIL) from None
            if response.is_error:
                if response.status_code in {401, 403}:
                    raise ValueError("Не удалось авторизоваться в Gmail")
                raise ValueError(ERROR_GMAIL)
            try:
                result = response.json()
            except json.JSONDecodeError:
                result = {}
            return {
                "sent": True,
                "operation": "send",
                "to": recipients,
                "subject": subject,
                "id": result.get("id") if isinstance(result, dict) else None,
                "thread_id": result.get("threadId") if isinstance(result, dict) else None,
            }
        await self._send_smtp(node, payload, variables, recipients, subject, body, from_email)
        return {"sent": True, "operation": "send", "to": recipients, "subject": subject, "id": None}

    async def _send_smtp(
        self,
        node: GmailNode,
        payload: object,
        variables: dict,
        recipients: list[str],
        subject: str,
        body: str,
        from_email: str,
    ) -> None:
        username = render_template(node.smtp_username, payload, variables).strip()
        password = rendered_secret(node.smtp_password, payload, variables)
        host = render_template(node.smtp_host or "smtp.gmail.com", payload, variables).strip() or "smtp.gmail.com"
        sender = from_email or username
        if not username or not password or not sender:
            raise ValueError("Укажите почту Gmail и пароль приложения")
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body or "")

        def deliver() -> None:
            with smtplib.SMTP(host, int(node.smtp_port or 587), timeout=30) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(message)

        try:
            await asyncio.to_thread(deliver)
        except smtplib.SMTPAuthenticationError:
            raise ValueError("Не удалось авторизоваться в Gmail") from None
        except (smtplib.SMTPException, OSError, TimeoutError):
            raise ValueError(ERROR_GMAIL) from None

    async def _list(self, node: GmailNode, payload: object, variables: dict) -> dict:
        token = rendered_secret(node.access_token, payload, variables)
        if not token:
            raise ValueError("Для чтения писем укажите OAuth-токен Gmail")
        query = render_template(node.query, payload, variables).strip()
        params: dict[str, str | int] = {"maxResults": int(node.max_results or 10)}
        if query:
            params["q"] = query
        try:
            listed = await self.client.get(
                _GMAIL_LIST_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=settings.provider_timeout_seconds,
            )
        except httpx.RequestError:
            raise ValueError(ERROR_GMAIL) from None
        if listed.is_error:
            if listed.status_code in {401, 403}:
                raise ValueError("Не удалось авторизоваться в Gmail")
            raise ValueError(ERROR_GMAIL)
        try:
            listing = listed.json()
        except json.JSONDecodeError:
            raise ValueError(ERROR_GMAIL) from None
        refs = listing.get("messages") if isinstance(listing, dict) else None
        messages: list[dict] = []
        for ref in refs or []:
            if not isinstance(ref, dict) or not ref.get("id"):
                continue
            try:
                detail = await self.client.get(
                    f"{_GMAIL_LIST_URL}/{ref['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                    timeout=settings.provider_timeout_seconds,
                )
            except httpx.RequestError:
                raise ValueError(ERROR_GMAIL) from None
            if detail.is_error:
                continue
            try:
                item = detail.json()
            except json.JSONDecodeError:
                continue
            payload_headers = (item.get("payload") or {}).get("headers") if isinstance(item, dict) else []
            headers = payload_headers if isinstance(payload_headers, list) else []
            messages.append({
                "id": item.get("id"),
                "thread_id": item.get("threadId"),
                "snippet": item.get("snippet") or "",
                "subject": _header_value(headers, "Subject"),
                "from": _header_value(headers, "From"),
                "date": _header_value(headers, "Date"),
            })
        return {"operation": "list", "messages": messages, "count": len(messages)}
