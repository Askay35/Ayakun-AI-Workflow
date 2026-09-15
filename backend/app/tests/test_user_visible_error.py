from fastapi import HTTPException
import httpx

from schemas.workflow import NodeType
from services.execution.errors import ERROR_GENERIC, ERROR_TELEGRAM, user_visible_error


def test_user_visible_error_keeps_safe_value_error() -> None:
    assert user_visible_error(ValueError("Переменная count пока не определена")) == (
        "Переменная count пока не определена"
    )


def test_user_visible_error_hides_httpx_telegram_url() -> None:
    request = httpx.Request(
        "POST",
        "https://api.telegram.org/bot123456789:SECRET_BOT_TOKEN_VALUE/sendMessage",
    )
    response = httpx.Response(400, request=request)
    exc = httpx.HTTPStatusError("Client error '400 Bad Request' for url", request=request, response=response)
    message = user_visible_error(exc, NodeType.TELEGRAM_SEND)
    assert message == ERROR_TELEGRAM
    assert "SECRET_BOT_TOKEN_VALUE" not in message
    assert "400" not in message
    assert "telegram.org" not in message


def test_user_visible_error_hides_unsafe_http_exception_detail() -> None:
    exc = HTTPException(
        400,
        "Client error '400 Bad Request' for url 'https://api.telegram.org/bot123:SECRET/sendMessage'",
    )
    assert user_visible_error(exc, NodeType.TELEGRAM_SEND) == ERROR_TELEGRAM


def test_user_visible_error_generic_without_node_type() -> None:
    assert user_visible_error(RuntimeError("boom")) == ERROR_GENERIC
