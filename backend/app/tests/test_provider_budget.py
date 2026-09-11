from types import SimpleNamespace

import pytest

from services.providers import OpenAICompatibleProvider, prompt_input


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(
            input_tokens=120,
            output_tokens=50,
            input_tokens_details=SimpleNamespace(cached_tokens=80),
        )
        return SimpleNamespace(
            output_text="частичный результат",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=usage,
        )


@pytest.mark.asyncio
async def test_provider_makes_one_call_and_preserves_truncated_result() -> None:
    provider = object.__new__(OpenAICompatibleProvider)
    responses = FakeResponses()
    provider.client = SimpleNamespace(responses=responses)
    provider.model = "deepseek-v4-flash"

    result = await provider.prompt(
        "Сделай отчёт",
        instructions="Кратко",
        input_data=["данные"],
        max_tokens=50,
    )

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["instructions"] == "Кратко"
    assert call["input"] == prompt_input("Сделай отчёт", ["данные"])
    assert call["max_output_tokens"] == 50
    assert "messages" not in call
    assert result.text == "частичный результат"
    assert result.truncated is True
    assert result.usage.input_tokens == 120
    assert result.usage.input_cache_hit_tokens == 80
    assert result.usage.input_cache_miss_tokens == 40
    assert result.usage.output_tokens == 50


@pytest.mark.asyncio
async def test_provider_appends_output_format_to_instructions() -> None:
    provider = object.__new__(OpenAICompatibleProvider)
    responses = FakeResponses()
    provider.client = SimpleNamespace(responses=responses)
    provider.model = "deepseek-v4-flash"

    await provider.prompt(
        "Сделай отчёт",
        instructions="Кратко",
        output_format='{"json": {"ok": true}}',
    )

    call = responses.calls[0]
    assert call["instructions"].startswith("Кратко")
    assert '{"json": {"ok": true}}' in call["instructions"]
    assert "Верни результат в следующем формате:" in call["instructions"]


def test_prompt_input_appends_connected_parent_data() -> None:
    assert prompt_input("Сделай вывод") == "Сделай вывод"
    assert prompt_input("Сделай вывод", ["новость A"]) == "Сделай вывод\n\nновость A"
