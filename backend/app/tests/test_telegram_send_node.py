import pytest

from helper import render_template
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
