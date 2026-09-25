"""Общий вызов внешних API для узлов-интеграций: понятные ошибки без URL и токенов."""

from __future__ import annotations

import json

import httpx

from core.config import settings


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return ""
    message: object = None
    if isinstance(body, dict):
        for key in ("message", "error_description", "error", "errorMessages", "errors"):
            value = body.get(key)
            if value:
                message = value
                break
    if isinstance(message, dict):
        message = message.get("message") or "; ".join(f"{key}: {value}" for key, value in message.items())
    if isinstance(message, list):
        message = "; ".join(str(item) for item in message)
    text = str(message or "").strip()
    return f" — {text[:240]}" if text else ""


async def call_api(
    client: httpx.AsyncClient,
    service: str,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    try:
        response = await client.request(method, url, timeout=settings.provider_timeout_seconds, **kwargs)
    except httpx.RequestError:
        raise ValueError(f"{service}: сервис недоступен, попробуйте позже") from None
    if response.status_code in {401, 403}:
        raise ValueError(f"{service}: доступ запрещён — проверьте токен и права доступа")
    if response.status_code == 404:
        raise ValueError(f"{service}: объект не найден — проверьте идентификаторы")
    if response.status_code == 429:
        raise ValueError(f"{service}: слишком много запросов, попробуйте позже")
    if response.is_error:
        raise ValueError(f"{service}: ошибка {response.status_code}{_detail(response)}")
    return response


def response_json(response: httpx.Response, service: str) -> object:
    if not response.content:
        return {}
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        raise ValueError(f"{service}: сервис вернул неожиданный ответ") from None


def require_https(url: str, service: str) -> str:
    text = (url or "").strip().rstrip("/")
    if not text.startswith("https://"):
        raise ValueError(f"{service}: адрес должен начинаться с https://")
    return text
