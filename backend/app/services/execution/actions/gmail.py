from __future__ import annotations

import base64
import json
from email.message import EmailMessage

import httpx

from core.config import settings
from core.user_errors import ERROR_GMAIL
from helper import apply_variable_assignments, render_template
from schemas.workflow import GmailNode
from services.execution.actions.base import NodeAction
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


def _bearer_token(node: GmailNode, context: dict) -> str:
    tokens = context.get("gmail_tokens")
    account_id = node.gmail_account_id
    token = tokens.get(account_id) if isinstance(tokens, dict) and account_id is not None else None
    if not isinstance(token, str) or not token.strip():
        raise ValueError(
            "Не удалось авторизоваться в Gmail" if token == "" else "Войдите в Google в этом звене"
        )
    return token.strip()


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
        token = _bearer_token(node, context)
        if node.operation == "list":
            output = await self._list(node, payload, variables, token)
        else:
            output = await self._send(node, payload, variables, token)
        apply_variable_assignments(node.assignments, output, context)
        return output

    async def _send(self, node: GmailNode, payload: object, variables: dict, token: str) -> dict:
        to = render_template(node.to, payload, variables).strip()
        subject = render_template(node.subject, payload, variables)
        body = render_template(node.body, payload, variables)
        from_email = render_template(node.from_email, payload, variables).strip()
        recipients = _split_recipients(to)
        if not recipients:
            raise ValueError("Укажите получателя письма")
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

    async def _list(self, node: GmailNode, payload: object, variables: dict, token: str) -> dict:
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
