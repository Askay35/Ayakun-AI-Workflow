import pytest

from helper import display_telegram_output, render_telegram_message, render_template, unescape_telegram_markdown
from schemas.workflow import TelegramSendNode
from services.execution import DefaultExecutors
from services.media_files import write_temp_bytes


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


def test_render_template_root_placeholder_dumps_json() -> None:
    payload = [{"title": "BTC", "price": 1.2}]
    assert render_template("{{$}}", payload) == '[{"title": "BTC", "price": 1.2}]'


def test_render_template_for_loop_over_json_path() -> None:
    payload = {"data": [{"label": "BTC", "price": 12}, {"label": "ETH", "price": 8}]}
    rendered = render_template(
        "{% for item in $data %}Название: {{item.label}} цена: {{item.price}}\n{% endfor %}",
        payload,
    )
    assert rendered == "Название: BTC цена: 12\nНазвание: ETH цена: 8\n"


def test_render_template_for_loop_over_variable() -> None:
    rendered = render_template(
        "{% for row in rows %}{{row.title}} {% endfor %}",
        {},
        {"rows": [{"title": "A"}, {"title": "B"}]},
    )
    assert rendered == "A B "


def test_render_template_for_loop_rejects_taken_variable_name() -> None:
    with pytest.raises(ValueError, match="В цикле используется занятое имя переменной"):
        render_template(
            "{% for item in $data %}{{item.title}}{% endfor %}",
            {"data": [{"title": "BTC"}]},
            {"item": "занято"},
        )


def test_render_template_for_loop_allows_other_name_when_item_exists() -> None:
    rendered = render_template(
        "{% for row in $data %}{{row.title}} {{item}}{% endfor %}",
        {"data": [{"title": "BTC"}]},
        {"item": "ok"},
    )
    assert rendered == "BTC ok"


def test_render_telegram_message_root_and_loop() -> None:
    payload = [{"title": "BTC", "symbol": "BTC"}]
    dumped = render_telegram_message("{{$}}", payload)
    assert "BTC" in dumped
    assert "title" in dumped.replace("\\", "")
    looped = render_telegram_message(
        "{% for item in $ %}*{{item.title}}* {{item.symbol}}\n{% endfor %}",
        payload,
    )
    assert "*BTC*" in looped



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
        self.bot_tokens: list[str | None] = []
        self.files: list[tuple[str, bytes, str, str, str | None]] = []

    async def send(self, chat_id: str, text: str, bot_token: str | None = None) -> None:
        self.sent.append((chat_id, text))
        self.bot_tokens.append(bot_token)

    async def send_file(
        self,
        chat_id: str,
        data: bytes,
        filename: str,
        mime: str,
        caption: str | None = None,
        bot_token: str | None = None,
    ) -> None:
        self.files.append((chat_id, data, filename, mime, caption))
        self.bot_tokens.append(bot_token)


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
async def test_telegram_sends_generated_image_with_caption_and_file_only() -> None:
    path = write_temp_bytes(b"\xff\xd8\xffcat", ".jpg")
    picture = {"source": "generated", "mime": "image/jpeg", "filename": "image.jpg", "path": path}

    with_text = object.__new__(DefaultExecutors)
    with_text.notifications = FakeNotifications()
    result = await with_text.telegram_send(
        TelegramSendNode(id="tg", chat_id=42, message="Кот", parents=["gen"]),
        {"nodes": {"gen": {"type": "image_generation", "output": picture}}},
    )
    assert result["sent"] is True
    assert result["file"] == "image.jpg"
    assert with_text.notifications.files == [("42", b"\xff\xd8\xffcat", "image.jpg", "image/jpeg", "Кот")]
    assert with_text.notifications.sent == []

    file_only = object.__new__(DefaultExecutors)
    file_only.notifications = FakeNotifications()
    result = await file_only.telegram_send(
        TelegramSendNode(id="tg", chat_id=42, parents=["disk"]),
        {"nodes": {"disk": {"type": "yandex_disk", "output": {**picture, "source": "yandex", "filename": "from-disk.png", "mime": "image/png"}}}},
    )
    assert result["text"] == ""
    assert result["file"] == "from-disk.png"
    assert file_only.notifications.sent == []
    assert file_only.notifications.files[0][2:] == ("from-disk.png", "image/png", None)


@pytest.mark.asyncio
async def test_telegram_send_dumps_json_array_when_message_empty() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(id="tg", chat_id=42, parents=["transform"])
    payload = [{"title": "BTC", "symbol": "BTC", "percent_change_24h": 1.2}]
    result = await executors.telegram_send(node, {
        "nodes": {
            "transform": {
                "type": "data_transform",
                "output": payload,
            }
        }
    })
    assert "BTC" in result["text"]
    assert "percent\\_change\\_24h" in result["text"] or "percent_change_24h" in result["text"].replace("\\", "")
    assert "1\\.2" in result["text"] or "1.2" in result["text"].replace("\\", "")
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_telegram_send_renders_root_placeholder() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(id="tg", chat_id=42, message="{{$}}", parents=["transform"])
    payload = [{"title": "ETH"}]
    result = await executors.telegram_send(node, {
        "nodes": {
            "transform": {
                "type": "data_transform",
                "output": payload,
            }
        }
    })
    assert "ETH" in result["text"]
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_telegram_provider_uses_markdown_and_hides_http_errors(monkeypatch) -> None:
    import json
    import httpx

    from core.config import settings
    from services.execution.errors import ERROR_TELEGRAM
    from services.providers import TelegramNotificationProvider

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.setdefault("url", str(request.url))
        captured.setdefault("body", json.loads(request.content))
        captured["calls"] = captured.get("calls", 0) + 1
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"})

    monkeypatch.setattr(settings, "telegram_bot_token", "123456789:SECRET_BOT_TOKEN_VALUE")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TelegramNotificationProvider(client)
        with pytest.raises(ValueError, match=ERROR_TELEGRAM) as raised:
            await provider.send("42", "Цена: 12.5 — {{value}}")
    assert raised.value.__cause__ is None
    assert captured["body"]["parse_mode"] == "MarkdownV2"
    assert captured["calls"] == 2  # повтор без форматирования
    assert captured["body"]["text"] == "Цена: 12.5 — {{value}}"
    assert "SECRET_BOT_TOKEN_VALUE" not in str(raised.value)
    assert "400" not in str(raised.value)
    assert "api.telegram.org" not in str(raised.value)


def test_telegram_send_node_coerces_numeric_chat_id() -> None:
    node = TelegramSendNode(id="tg", chat_id=42, message="hi")
    assert node.chat_id == "42"
    assert node.chat_id_blank() is False
    assert node.uses_custom_bot() is False


@pytest.mark.asyncio
async def test_telegram_send_renders_chat_id_from_json_path() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(
        id="tg",
        chat_id="{{$body.message.chat.id}}",
        message="Привет",
        parents=["webhook"],
    )
    result = await executors.telegram_send(node, {
        "nodes": {
            "webhook": {
                "type": "webhook",
                "output": {"body": {"message": {"chat": {"id": 555}}}},
            }
        }
    })
    assert result["sent"] is True
    assert executors.notifications.sent == [("555", "Привет")]
    assert executors.notifications.bot_tokens == [None]


@pytest.mark.asyncio
async def test_telegram_send_renders_chat_id_from_variable() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(id="tg", chat_id="{{field}}", message="ok", parents=["http"])
    result = await executors.telegram_send(node, {
        "variables": {"field": "-100123"},
        "nodes": {
            "http": {
                "type": "http_request",
                "output": {"ok": True},
            }
        }
    })
    assert result == {"sent": True, "text": "ok"}
    assert executors.notifications.sent == [("-100123", "ok")]


@pytest.mark.asyncio
async def test_telegram_send_passes_custom_bot_token() -> None:
    executors = object.__new__(DefaultExecutors)
    executors.notifications = FakeNotifications()
    node = TelegramSendNode(
        id="tg",
        chat_id="99",
        bot_token="123456789:CUSTOM_BOT_TOKEN",
        message="hi",
        parents=["http"],
    )
    await executors.telegram_send(node, {
        "nodes": {
            "http": {
                "type": "http_request",
                "output": {"ok": True},
            }
        }
    })
    assert executors.notifications.sent == [("99", "hi")]
    assert executors.notifications.bot_tokens == ["123456789:CUSTOM_BOT_TOKEN"]


@pytest.mark.asyncio
async def test_telegram_provider_uses_custom_bot_token(monkeypatch) -> None:
    import json
    import httpx

    from core.config import settings
    from services.providers import TelegramNotificationProvider

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(settings, "telegram_bot_token", "PLATFORM_TOKEN")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TelegramNotificationProvider(client)
        await provider.send("42", "hi", bot_token="999:CUSTOM_TOKEN")
    assert captured["url"] == "https://api.telegram.org/bot999:CUSTOM_TOKEN/sendMessage"
    assert captured["body"]["chat_id"] == "42"
    assert "PLATFORM_TOKEN" not in captured["url"]


def test_telegram_custom_bot_requires_chat_id() -> None:
    from schemas.workflow import WorkflowGraph
    from services.workflow import validate_graph

    graph = WorkflowGraph(nodes=[
        TelegramSendNode(id="tg", bot_token="123:ABC", message="hi"),
    ])
    errors = validate_graph(graph, strict=True)
    assert any("chat_id" in item for item in errors)
