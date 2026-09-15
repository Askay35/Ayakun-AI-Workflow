import pytest

from helper import display_telegram_output, render_telegram_message, render_template, unescape_telegram_markdown
from schemas.workflow import TelegramSendNode
from services.execution import DefaultExecutors


def test_render_template_reads_from_payload_root() -> None:
    payload = {"data": [{"price": 123}]}
    assert render_template("Цена: {{$data[0].price}}", payload) == "Цена: 123"
    assert render_template("Цена: {{$data.0.price}}", payload) == "Цена: 123"


def test_render_template_substitutes_workflow_variable() -> None:
    assert render_template("Привет, {{name}}", {}, {"name": "Амир"}) == "Привет, Амир"
    assert render_template("Цена: {{price}}", {"data": [{"price": 1}]}, {"price": 123}) == "Цена: 123"


def test_render_template_keeps_legacy_json_prefix() -> None:
    assert render_template("id={{$json.userId}}", {"userId": 7}) == "id=7"
    assert render_template("id={{$json.userId}}", {"json": {"userId": 7}}) == "id=7"


def test_render_telegram_message_escapes_values_and_keeps_markup() -> None:
    assert render_telegram_message("Цена: {{price}}.", {}, {"price": 12.5}) == "Цена: 12\\.5\\."
    assert render_telegram_message("*Скидка:* {{price}}!", {}, {"price": "50%"}) == "*Скидка:* 50%\\!"
    assert render_telegram_message(
        "[Открыть]({{url}})",
        {},
        {"url": "https://example.com/a.b"},
    ) == "[Открыть](https://example.com/a.b)"
    assert render_telegram_message("Привет, {{name}}", {}, {"name": "O_Neal"}) == "Привет, O\\_Neal"
    assert render_telegram_message("`{{code}}`", {}, {"code": "a.b"}) == "`a.b`"


def test_unescape_telegram_markdown_for_run_page() -> None:
    assert unescape_telegram_markdown("A \\=\\= B") == "A == B"
    assert unescape_telegram_markdown("*Цена:* 12\\.5 руб\\.") == "*Цена:* 12.5 руб."
    assert display_telegram_output({"sent": True, "text": "A \\=\\= B"}) == {
        "sent": True,
        "text": "A == B",
    }


class FakeNotifications:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_telegram_send_renders_message_from_parent() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(
        id="tg",
        chat_id=42,
        message="Цена: {{$data[0].price}}",
        parents=["http"],
    )
    result = await executors.telegram_send(node, {
        "nodes": {
            "http": {
                "type": "http_request",
                "output": {"data": [{"price": 123}]},
            }
        }
    })
    assert result == {"sent": True, "text": "Цена: 123"}
    assert executors.notifications.sent == [("42", "Цена: 123")]


@pytest.mark.asyncio
async def test_telegram_send_raises_when_path_missing() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(
        id="tg",
        chat_id=42,
        message="Цена: {{$data[0].price}}",
        parents=["http"],
    )
    with pytest.raises(ValueError, match="нет поля data\\[0\\].price"):
        await executors.telegram_send(node, {
            "nodes": {
                "http": {
                    "type": "http_request",
                    "output": {"ok": True},
                }
            }
        })
    assert executors.notifications.sent == []


@pytest.mark.asyncio
async def test_telegram_send_escapes_interpolated_markdown() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(
        id="tg",
        chat_id=42,
        message="*Цена:* {{$data[0].price}} руб.",
        parents=["http"],
    )
    result = await executors.telegram_send(node, {
        "nodes": {
            "http": {
                "type": "http_request",
                "output": {"data": [{"price": 12.5}]},
            }
        }
    })
    assert result == {"sent": True, "text": "*Цена:* 12\\.5 руб\\."}
    assert executors.notifications.sent == [("42", "*Цена:* 12\\.5 руб\\.")]


@pytest.mark.asyncio
async def test_telegram_send_uses_parent_text_when_message_empty() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(id="tg", chat_id=42, parents=["prompt"])
    result = await executors.telegram_send(node, {
        "nodes": {
            "prompt": {
                "type": "prompt",
                "output": {"text": "Готовый отчёт"},
            }
        }
    })
    assert result == {"sent": True, "text": "Готовый отчёт"}
    assert executors.notifications.sent == [("42", "Готовый отчёт")]


@pytest.mark.asyncio
async def test_telegram_provider_uses_markdown_and_hides_http_errors(monkeypatch) -> None:
    import json
    import httpx

    from core.config import settings
    from services.execution.errors import ERROR_TELEGRAM
    from services.providers import TelegramNotificationProvider

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"})

    monkeypatch.setattr(settings, "telegram_bot_token", "123456789:SECRET_BOT_TOKEN_VALUE")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TelegramNotificationProvider(client)
        with pytest.raises(ValueError, match=ERROR_TELEGRAM) as raised:
            await provider.send("42", "Цена: 12.5 — {{value}}")
    assert raised.value.__cause__ is None
    assert captured["body"]["parse_mode"] == "MarkdownV2"
    assert captured["body"]["text"] == "Цена: 12.5 — {{value}}"
    assert "SECRET_BOT_TOKEN_VALUE" not in str(raised.value)
    assert "400" not in str(raised.value)
    assert "api.telegram.org" not in str(raised.value)
