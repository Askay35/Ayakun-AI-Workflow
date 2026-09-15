"""Тексты ошибок, которые можно показать пользователю в карточке запуска."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from core.user_errors import (
    ERROR_GENERIC,
    ERROR_HTTP,
    ERROR_IF_ELSE,
    ERROR_PROMPT,
    ERROR_SEARCH,
    ERROR_TELEGRAM,
)
from schemas.workflow import NodeType

__all__ = [
    "ERROR_GENERIC",
    "ERROR_HTTP",
    "ERROR_IF_ELSE",
    "ERROR_PROMPT",
    "ERROR_SEARCH",
    "ERROR_TELEGRAM",
    "fallback_error",
    "is_safe_user_error",
    "user_visible_error",
]

_UNSAFE_ERROR_RE = re.compile(
    r"https?://|www\.|api\.telegram|/bot\d|traceback|file://|for url |status code|bad request",
    re.I,
)

_FALLBACKS: dict[str, str] = {
    NodeType.TELEGRAM_SEND.value: ERROR_TELEGRAM,
    NodeType.HTTP_REQUEST.value: ERROR_HTTP,
    NodeType.WEB_SEARCH.value: ERROR_SEARCH,
    NodeType.PROMPT.value: ERROR_PROMPT,
    NodeType.IF_ELSE.value: ERROR_IF_ELSE,
}


def is_safe_user_error(message: str) -> bool:
    text = (message or "").strip()
    if not text or len(text) > 400:
        return False
    if _UNSAFE_ERROR_RE.search(text):
        return False
    if "Client error" in text or "Server error" in text:
        return False
    return True


def _node_type_value(node_type: Any) -> str | None:
    if node_type is None:
        return None
    return getattr(node_type, "value", None) or str(node_type)


def fallback_error(node_type: Any = None) -> str:
    key = _node_type_value(node_type)
    if key:
        return _FALLBACKS.get(key, ERROR_GENERIC)
    return ERROR_GENERIC


def user_visible_error(exc: BaseException, node_type: Any = None) -> str:
    """Сообщение для NodeRun/WorkflowRun: без URL, токенов и сырых ответов провайдеров."""
    fallback = fallback_error(node_type)
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str) and is_safe_user_error(detail):
            return detail
        return fallback
    message = str(exc).strip()
    if isinstance(exc, ValueError) and is_safe_user_error(message):
        return message
    return fallback
