import json

import pytest

from helper import form_request_body, json_root_from_output
from schemas.workflow import HttpRequestNode, PromptNode, TelegramSendNode, WorkflowGraph
from services.execution import DefaultExecutors, output_text
from services.providers import llm_instructions
from services.workflow import validate_graph


REQUEST_TEMPLATE = """{
  "method": "GET",
  "url": "https://api.example.com/users/{{$json.userId}}",
  "headers": {
    "Authorization": "Bearer ..."
  },
  "body": {
    "email": "{{$json.email}}"
  }
}"""


def test_form_request_body_substitutes_json_expressions() -> None:
    result = form_request_body(
        REQUEST_TEMPLATE,
        {"json": {"userId": 123, "email": "john@example.com"}},
    )
    assert result == {
        "method": "GET",
        "url": "https://api.example.com/users/123",
        "headers": {"Authorization": "Bearer ..."},
        "body": {"email": "john@example.com"},
    }


def test_form_request_body_uses_flat_parent_payload() -> None:
    result = form_request_body(REQUEST_TEMPLATE, {"userId": "123", "email": "user@example.com"})
    assert result["url"].endswith("/users/123")
    assert result["body"]["email"] == "user@example.com"


def test_form_request_body_raises_on_missing_expression() -> None:
    with pytest.raises(ValueError, match=r"нет поля json.userId"):
        form_request_body(REQUEST_TEMPLATE, {"email": "user@example.com"})


def test_form_request_body_resolves_array_paths() -> None:
    result = form_request_body(
        '{"method":"GET","url":"https://api.example.com/{{$data[0].price}}"}',
        {"data": [{"price": 123}]},
    )
    assert result["url"] == "https://api.example.com/123"
    dotted = form_request_body(
        '{"method":"GET","url":"https://api.example.com/{{$data.0.price}}"}',
        {"data": [{"price": 123}]},
    )
    assert dotted["url"] == "https://api.example.com/123"


def test_form_request_body_raises_on_malformed_json() -> None:
    with pytest.raises(ValueError, match="некорректный JSON"):
        form_request_body("{not json", {"userId": 1})


def test_json_root_from_prompt_text() -> None:
    output = {
        "text": json.dumps({
            "json": {"userId": "123", "email": "user@example.com"},
        }),
        "usage": {"output_tokens": 10},
    }
    root = json_root_from_output(output)
    result = form_request_body(REQUEST_TEMPLATE, root)
    assert result["url"] == "https://api.example.com/users/123"
    assert result["body"]["email"] == "user@example.com"


def test_llm_instructions_keep_empty_format_unchanged() -> None:
    assert llm_instructions(None, None) is None
    assert llm_instructions("Кратко", "") == "Кратко"
    assert llm_instructions("Кратко", None) == "Кратко"


def test_llm_instructions_append_output_format_after_user_text() -> None:
    combined = llm_instructions("Отвечай кратко", '{"json": {"userId": "1"}}')
    assert combined is not None
    assert combined.startswith("Отвечай кратко")
    assert '{"json": {"userId": "1"}}' in combined
    assert "Верни результат в следующем формате:" in combined
    assert "markdown" in combined


def test_output_text_serializes_http_json() -> None:
    text = output_text({"userId": "123", "email": "user@example.com"})
    assert "123" in text
    assert "user@example.com" in text


def test_http_request_allows_zero_or_one_incoming_link() -> None:
    with_parent = WorkflowGraph(nodes=[
        PromptNode(id="prompt", prompt="Найди пользователя"),
        HttpRequestNode(id="http", request_json=REQUEST_TEMPLATE, parents=["prompt"]),
        TelegramSendNode(id="tg", parents=["http"]),
    ])
    assert validate_graph(with_parent, strict=True) == []

    as_start = WorkflowGraph(nodes=[
        HttpRequestNode(id="http", request_json=REQUEST_TEMPLATE),
    ])
    assert validate_graph(as_start, strict=True) == []

    too_many = WorkflowGraph(nodes=[
        PromptNode(id="a", prompt="A", children=["http"]),
        PromptNode(id="b", prompt="B", children=["http"]),
        HttpRequestNode(id="http", request_json=REQUEST_TEMPLATE, parents=["a", "b"]),
    ])
    errors = validate_graph(too_many, strict=True)
    assert any("только одну входящую связь" in item for item in errors)


class FakeHttpResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.content = json.dumps(payload).encode()
        self.text = json.dumps(payload)
        self.is_error = status >= 400

    def json(self) -> dict:
        return self._payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def request(self, **kwargs):
        self.calls.append(kwargs)
        return FakeHttpResponse({"id": 123, "ok": True})


@pytest.mark.asyncio
async def test_http_request_executor_resolves_parent_output() -> None:
    executors = object.__new__(DefaultExecutors)
    client = FakeHttpClient()
    executors.client = client
    node = HttpRequestNode(id="http", request_json=REQUEST_TEMPLATE, parents=["prompt"])
    context = {
        "nodes": {
            "prompt": {
                "type": "prompt",
                "output": {
                    "text": json.dumps({"json": {"userId": "123", "email": "user@example.com"}}),
                },
            }
        }
    }
    result = await executors.http_request(node, context)
    assert result == {"id": 123, "ok": True}
    call = client.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.example.com/users/123"
    assert call["json"] == {"email": "user@example.com"}
