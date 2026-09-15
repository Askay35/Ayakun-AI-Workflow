import json
import logging

import httpx
import pytest
import requests

from core.logging import (
    JsonFormatter,
    install_outbound_http_logging,
    output_preview,
    sanitize_url,
)
import core.logging as logging_mod


def test_output_preview_keeps_ai_usage() -> None:
    preview = output_preview({
        "text": "итог",
        "model": "deepseek-flash",
        "truncated": False,
        "usage": {"input_tokens": 59, "output_tokens": 331},
    })
    payload = json.loads(preview)
    assert payload["text"] == "итог"
    assert payload["usage"]["output_tokens"] == 331


def test_json_formatter_includes_event_and_credits() -> None:
    record = logging.LogRecord(
        name="execution.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Звено выполнено",
        args=(),
        exc_info=None,
    )
    record.event = "node.succeeded"
    record.credits = "0.23144"
    record.node_type = "prompt"
    line = JsonFormatter("worker").format(record)
    payload = json.loads(line)
    assert payload["event"] == "node.succeeded"
    assert payload["credits"] == "0.23144"
    assert payload["service"] == "worker"
    assert payload["msg"] == "Звено выполнено"


def test_sanitize_url_strips_query() -> None:
    assert sanitize_url("https://api.example.com/v1/x?token=secret") == "https://api.example.com/v1/x"


def test_sanitize_url_redacts_telegram_bot_token() -> None:
    raw = "https://api.telegram.org/bot123456789:SECRET_BOT_TOKEN_VALUE/sendMessage"
    assert sanitize_url(raw) == "https://api.telegram.org/bot[redacted]/sendMessage"
    from core.logging import redact_secrets
    assert "SECRET_BOT_TOKEN_VALUE" not in redact_secrets(
        "Client error '400 Bad Request' for url 'https://api.telegram.org/bot123456789:SECRET_BOT_TOKEN_VALUE/sendMessage'"
    )


def test_install_outbound_http_logging_is_idempotent() -> None:
    install_outbound_http_logging()
    install_outbound_http_logging()
    assert callable(httpx.Client.send)
    assert callable(requests.Session.send)


@pytest.mark.asyncio
async def test_httpx_outbound_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    install_outbound_http_logging()
    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    with caplog.at_level(logging.INFO, logger="ayakun.http"):
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("https://example.test/ping?token=secret")
    assert response.status_code == 204
    records = [r for r in caplog.records if getattr(r, "event", None) == "http.outbound"]
    assert records
    record = records[-1]
    assert record.method == "GET"
    assert record.url == "https://example.test/ping"
    assert record.status_code == 204
    assert "secret" not in record.url


def test_requests_outbound_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    class FakeResponse:
        status_code = 201

    def fake_send(self, request, **kwargs):
        return FakeResponse()

    requests.Session.send = fake_send  # type: ignore[method-assign]
    logging_mod._HTTP_LOGGING_INSTALLED = False
    install_outbound_http_logging()

    prepared = requests.Request("POST", "https://yookassa.test/v3/payments").prepare()
    with caplog.at_level(logging.INFO, logger="ayakun.http"):
        response = requests.Session().send(prepared)
    assert response.status_code == 201
    records = [r for r in caplog.records if getattr(r, "event", None) == "http.outbound"]
    assert records
    assert records[-1].client == "requests"
    assert records[-1].path == "/v3/payments"
