import base64
import asyncio
import io
import json
import time
import uuid
import wave
from decimal import Decimal

import httpx
import pytest

from core.config import settings
from execution.tasks import node_cost
from schemas.workflow import (
    AudioTranscriptionNode,
    DelayNode,
    IfElseNode,
    ImageGenerationNode,
    ImageNode,
    ImageRecognitionNode,
    LoopNode,
    NodeType,
    PromptNode,
    WorkflowGraph,
    YandexDiskNode,
)
from services.execution.actions.audio_transcription import AudioTranscriptionAction
from services.execution.actions.delay import DelayAction
from services.execution.actions.if_else import IfElseAction
from services.execution.actions.image_generation import ImageGenerationAction
from services.execution.actions.image_recognition import ImageRecognitionAction
from services.execution.actions.loop import LOOP_MAX_ITERATIONS, LoopAction
from services.execution.actions.yandex_disk import YandexDiskAction
from services.media_files import write_temp_bytes
from services.gigachat import (
    TOKEN_FILE_MARGIN_SECONDS,
    TOKEN_TTL_SECONDS,
    GigaChatMediaProvider,
    parse_generated_image_id,
    reset_gigachat_token_cache,
)
import services.gigachat as gigachat
from services.pricing import (
    RUB_PER_CREDIT,
    audio_transcription_credits,
    billable_credits,
    credits_for_rubles,
    estimate_run_cost,
    image_generation_credits,
    image_recognition_credits,
    media_estimate_credits,
)
from services.pricing import PricingService
from services.workflow import validate_graph


@pytest.mark.asyncio
async def test_if_else_condition_still_evaluates() -> None:
    node = IfElseNode(id="iff", condition="{{$score}} >= 0.8", parents=["src"])
    context = {
        "nodes": {"src": {"type": "http_request", "output": {"score": 0.91}}},
        "variables": {},
    }
    result = await IfElseAction().execute(node, context)
    assert result["result"] is True
    assert result["branch"] == "TRUE"
    assert result["condition"] == "{{$score}} >= 0.8"


@pytest.mark.asyncio
async def test_loop_for_each_json_path_and_variable() -> None:
    by_path = LoopNode(id="loop", mode="for_each", source="{{$body.items}}", parents=["src"])
    path_out = await LoopAction().execute(by_path, {
        "nodes": {"src": {"type": "webhook", "output": {"body": {"items": ["a", "b"]}}}},
        "variables": {},
    })
    assert path_out["items"] == ["a", "b"]
    assert path_out["count"] == 2
    assert path_out["capped"] is False

    by_var = LoopNode(id="loop", mode="for_each", source="{{rows}}")
    var_out = await LoopAction().execute(by_var, {"variables": {"rows": [{"id": 1}]}, "input": {}})
    assert var_out["items"] == [{"id": 1}]
    assert var_out["count"] == 1


@pytest.mark.asyncio
async def test_loop_times_and_cap() -> None:
    counted = await LoopAction().execute(
        LoopNode(id="loop", mode="times", times="{{n}}"),
        {"variables": {"n": 4}, "input": {}},
    )
    assert counted["items"] == [1, 2, 3, 4]
    capped = await LoopAction().execute(
        LoopNode(id="loop", mode="times", times="1000"),
        {"variables": {}, "input": {}},
    )
    assert capped["count"] == LOOP_MAX_ITERATIONS
    assert capped["capped"] is True
    with pytest.raises(ValueError, match="не меньше 1"):
        await LoopAction().execute(LoopNode(id="loop", mode="times", times="0"), {"variables": {}, "input": {}})


@pytest.mark.asyncio
async def test_loop_while_stops_or_hits_cap() -> None:
    stopped = await LoopAction().execute(
        LoopNode(id="loop", mode="while", while_variable="n", while_operator="<", while_value="0"),
        {"variables": {"n": 3}, "input": {}},
    )
    assert stopped["count"] == 0
    assert stopped["capped"] is False

    running = await LoopAction().execute(
        LoopNode(id="loop", mode="while", while_variable="n", while_operator=">", while_value="0"),
        {"variables": {"n": 3}, "input": {}},
    )
    assert running["count"] == LOOP_MAX_ITERATIONS
    assert running["capped"] is True
    assert running["items"][0] == {"index": 1, "item": 3}


@pytest.mark.asyncio
async def test_delay_clamps(monkeypatch) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("services.execution.actions.delay.asyncio.sleep", fake_sleep)
    short = await DelayAction().execute(DelayNode(id="d", amount="0.35", unit="seconds"), {"input": {}})
    assert short["waited_seconds"] == pytest.approx(0.35)
    high = await DelayAction().execute(DelayNode(id="d", amount="9999", unit="seconds"), {"input": {}})
    assert high["waited_seconds"] == 3600
    minutes = await DelayAction().execute(DelayNode(id="d", amount="90", unit="minutes"), {"input": {}})
    assert minutes["waited_seconds"] == 3600
    negative = await DelayAction().execute(DelayNode(id="d", amount="-2", unit="seconds"), {"input": {}})
    assert negative["waited_seconds"] == 0
    assert slept == [pytest.approx(0.35), 3600, 3600, 0]


def test_media_pricing_matches_ruble_pack() -> None:
    assert RUB_PER_CREDIT == Decimal("390") / Decimal("2000")
    assert image_generation_credits() == Decimal("50")
    assert image_recognition_credits() == Decimal("25")
    assert media_estimate_credits("image_generation") == Decimal("50")
    assert media_estimate_credits("image_recognition") == Decimal("25")

    minute_raw = credits_for_rubles(Decimal("0.5"))
    assert audio_transcription_credits(1) == minute_raw.quantize(Decimal("0.000001"))
    assert audio_transcription_credits(2) == (minute_raw * 2).quantize(Decimal("0.000001"))
    assert media_estimate_credits("audio_transcription") == billable_credits(minute_raw)
    assert media_estimate_credits("audio_transcription") == Decimal("3")
    assert media_estimate_credits("loop") == Decimal("0")
    assert media_estimate_credits("delay") == Decimal("0")


@pytest.mark.asyncio
async def test_node_cost_charges_fixed_media_credits() -> None:
    image_credits, units, details = await node_cost(None, ImageGenerationNode(id="g", prompt="cat"), {})  # type: ignore[arg-type]
    assert units == 0
    assert image_credits == image_generation_credits()
    assert details["provider"] == "gigachat"
    assert details["provider_cost_usd"]
    assert "deepseek" not in details["provider"]

    vision_credits, _, vision = await node_cost(None, ImageRecognitionNode(id="r", prompt="what"), {"text": "cat"})  # type: ignore[arg-type]
    assert vision_credits == Decimal("25")
    assert vision["provider"] == "deepseek"
    assert vision["model"] == "vision"

    audio_credits, minutes, audio = await node_cost(
        None,  # type: ignore[arg-type]
        AudioTranscriptionNode(id="a", source="url", url="https://example.com/a.wav"),
        {"duration_seconds": 61, "duration_minutes": 2, "text": "hi"},
    )
    assert minutes == 2
    assert audio_credits == audio_transcription_credits(2)
    assert audio["minutes"] == 2


@pytest.mark.asyncio
async def test_estimate_graph_reserves_rounded_media_credits() -> None:
    graph = WorkflowGraph(nodes=[
        ImageGenerationNode(id="gen", prompt="cat", children=["audio"]),
        AudioTranscriptionNode(id="audio", source="url", url="https://example.com/a.wav", parents=["gen"]),
    ])

    class Service(PricingService):
        def __init__(self) -> None:
            self.db = None  # type: ignore[assignment]

        async def get(self, provider: str, model: str):
            raise AssertionError("media estimate must not ask DeepSeek rates")

    estimate = await Service().estimate_graph(graph)
    assert estimate == Decimal("50") + Decimal("3")
    assert estimate == estimate_run_cost(graph)


def test_parse_generated_image_id() -> None:
    content = 'Ждите <img src="b28fbd4f-105a-43e0-ba5a-2faa80b1f43c" fuse="true"/> готово'
    assert parse_generated_image_id(content) == "b28fbd4f-105a-43e0-ba5a-2faa80b1f43c"
    with pytest.raises(ValueError):
        parse_generated_image_id("нет картинки")


@pytest.mark.asyncio
async def test_gigachat_token_request_shape(monkeypatch) -> None:
    reset_gigachat_token_cache()
    monkeypatch.setattr(settings, "gigachat_auth_key", "test-key")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "tok-1"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        token = await GigaChatMediaProvider(client)._access_token(client)
    assert token == "tok-1"
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    assert request.headers["authorization"] == "Basic test-key"
    assert request.headers["accept"] == "application/json"
    assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert request.headers["user-agent"] == "ayakun"
    uuid.UUID(request.headers["rquid"])
    assert request.content == b"scope=GIGACHAT_API_PERS"
    assert "test-key" not in (request.content.decode())


@pytest.mark.asyncio
async def test_gigachat_refreshes_token_before_file_window_closes(monkeypatch) -> None:
    reset_gigachat_token_cache()
    monkeypatch.setattr(settings, "gigachat_auth_key", "test-key")
    gigachat._cached_token = "old-token"
    gigachat._cached_key = "test-key"
    gigachat._cached_fetched_at = time.monotonic() - (TOKEN_TTL_SECONDS - TOKEN_FILE_MARGIN_SECONDS)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"access_token": "fresh-token"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        token = await GigaChatMediaProvider(client)._access_token(client)
    assert token == "fresh-token"
    assert calls == 1

    async with httpx.AsyncClient(transport=transport) as client:
        reused = await GigaChatMediaProvider(client)._access_token(client)
    assert reused == "fresh-token"
    assert calls == 1


@pytest.mark.asyncio
async def test_token_refresh_waits_until_the_file_operation_finishes(monkeypatch) -> None:
    reset_gigachat_token_cache()
    monkeypatch.setattr(settings, "gigachat_auth_key", "test-key")
    oauth_calls = 0
    release = asyncio.Event()
    in_chat = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        if request.url.path.endswith("/oauth"):
            oauth_calls += 1
            return httpx.Response(200, json={"access_token": f"tok-{oauth_calls}"})
        if request.url.path.endswith("/chat/completions"):
            if not in_chat.is_set():
                in_chat.set()
                await release.wait()
            return httpx.Response(200, json={
                "choices": [{"message": {"content": '<img src="file-1" fuse="true"/>'}}]
            })
        if request.url.path.endswith("/content"):
            return httpx.Response(200, content=b"\xff\xd8jpg")
        if request.url.path.endswith("/delete"):
            return httpx.Response(200, json={"id": "file-1"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GigaChatMediaProvider(client)
        first = asyncio.create_task(provider.generate_image("первая"))
        await in_chat.wait()
        gigachat._cached_fetched_at = time.monotonic() - TOKEN_TTL_SECONDS
        second = asyncio.create_task(provider.generate_image("вторая"))
        await asyncio.sleep(0.05)
        assert oauth_calls == 1
        release.set()
        await first
        await second
    assert oauth_calls == 2


@pytest.mark.asyncio
async def test_gigachat_image_flow_deletes_file(monkeypatch) -> None:
    reset_gigachat_token_cache()
    monkeypatch.setattr(settings, "gigachat_auth_key", "test-key")
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            assert body["function_call"] == "auto"
            assert body["model"] == "GigaChat"
            return httpx.Response(200, json={
                "choices": [{"message": {"content": '<img src="file-9" fuse="true"/>'}}]
            })
        if request.url.path.endswith("/content"):
            return httpx.Response(200, content=b"\xff\xd8jpg")
        if request.url.path.endswith("/delete"):
            return httpx.Response(200, json={"id": "file-9"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        data = await GigaChatMediaProvider(client).generate_image("нарисуй кота")
    assert data.startswith(b"\xff\xd8")
    assert ("POST", "/v1/files/file-9/delete") in calls


@pytest.mark.asyncio
async def test_image_recognition_uses_upload_and_attachments(monkeypatch) -> None:
    reset_gigachat_token_cache()
    monkeypatch.setattr(settings, "gigachat_auth_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "img-1", "bytes": 3})
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            assert body["model"] == "GigaChat-2-Max"
            assert "function_call" not in body
            assert body["messages"][0]["attachments"] == ["img-1"]
            return httpx.Response(200, json={"choices": [{"message": {"content": "рыжий кот"}}]})
        if request.url.path.endswith("/delete"):
            return httpx.Response(200, json={})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        media = GigaChatMediaProvider(client)
        result = await ImageRecognitionAction(media, client).execute(
            ImageRecognitionNode(id="vision", prompt="Что на фото?", parents=["img"]),
            {
                "nodes": {
                    "img": {
                        "type": "image",
                        "output": {"source": "file", "mime": "image/jpeg", "filename": "cat.jpg", "base64": "aGVsbG8="},
                    }
                },
                "variables": {},
            },
        )
    assert result["text"] == "рыжий кот"


@pytest.mark.asyncio
async def test_deepseek_vision_sends_base64_image_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_api_key", "ds-key")
    monkeypatch.setattr(settings, "deepseek_vision_model", "deepseek-v4-flash-vision-exp")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://api.deepseek.com")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "кот"}}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await ImageRecognitionAction(client=client).execute(
            ImageRecognitionNode(id="vision", prompt="", parents=["img"]),
            {
                "nodes": {
                    "img": {
                        "type": "image",
                        "output": {"source": "file", "mime": "image/png", "filename": "cat.png", "base64": "aGVsbG8="},
                    }
                },
                "variables": {},
            },
        )
    assert result["text"] == "кот"
    assert seen["url"] == "https://api.deepseek.com/chat/completions"
    assert seen["auth"] == "Bearer ds-key"
    content = seen["body"]["messages"][0]["content"]
    assert seen["body"]["model"] == "deepseek-v4-flash-vision-exp"
    assert content[0] == {"type": "text", "text": "Что изображено на картинке?"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,aGVsbG8="


@pytest.mark.asyncio
async def test_image_recognition_rejects_files_over_30mb() -> None:
    class Media:
        async def recognize_image(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
            raise AssertionError("файл больше лимита не должен уходить в модель")

    huge = base64.b64encode(b"x" * (30 * 1024 * 1024 + 1)).decode()
    with pytest.raises(ValueError, match="30 МБ"):
        await ImageRecognitionAction(Media()).execute(
            ImageRecognitionNode(id="vision", prompt="что это", parents=["img"]),
            {
                "nodes": {
                    "img": {
                        "type": "image",
                        "output": {"source": "file", "mime": "image/jpeg", "filename": "big.jpg", "base64": huge},
                    }
                },
                "variables": {},
            },
        )


def _wav(seconds: float) -> bytes:
    frames = int(8000 * seconds)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_audio_transcription_bills_wav_minutes(monkeypatch) -> None:
    class Media:
        async def transcribe_audio(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
            assert filename.endswith(".wav")
            return "раз два"

        async def generate_image(self, prompt: str) -> bytes:
            return b""

        async def recognize_image(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
            return ""

    import base64

    encoded = base64.b64encode(_wav(61)).decode()
    result = await AudioTranscriptionAction(Media()).execute(
        AudioTranscriptionNode(id="audio", source="file", filename="note.wav", file_base64=encoded),
        {"input": {}, "variables": {}},
    )
    assert result["text"] == "раз два"
    assert result["duration_minutes"] == 2
    assert result["duration_seconds"] == pytest.approx(61)


@pytest.mark.asyncio
async def test_yandex_disk_download_and_upload_are_mocked() -> None:
    downloaded: list[tuple[str, str]] = []
    uploaded: list[tuple[str, str]] = []

    class FakeDisk:
        def __init__(self, token: str):
            self.token = token

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def download(self, remote: str, dest: str) -> None:
            downloaded.append((self.token, remote))
            with open(dest, "wb") as handle:
                handle.write(b"\xff\xd8\xff")

        async def upload(self, src: str, remote: str) -> None:
            uploaded.append((src, remote))

    action = YandexDiskAction(client_factory=FakeDisk)
    saved = await action.execute(
        YandexDiskNode(id="disk", operation="download", token="secret-token", remote_path="/pics/{{name}}.jpg"),
        {"variables": {"name": "cat"}, "input": {}},
    )
    assert saved["source"] == "yandex"
    assert saved["path"]
    assert saved["mime"] == "image/jpeg"
    assert downloaded == [("secret-token", "/pics/cat.jpg")]
    assert "secret-token" not in json.dumps({key: value for key, value in saved.items() if key != "path"})

    sent = await action.execute(
        YandexDiskNode(id="disk", operation="upload", token="secret-token", remote_path="/out.txt", content="hello"),
        {"variables": {}, "input": {}},
    )
    assert sent["uploaded"] is True
    assert sent["remote_path"] == "/out.txt"
    assert uploaded and uploaded[0][1] == "/out.txt"

    picture = write_temp_bytes(b"\xff\xd8\xffjpeg", ".jpg")
    await action.execute(
        YandexDiskNode(id="save", operation="upload", token="secret-token", remote_path="/pics/cat.jpg", parents=["gen"]),
        {
            "variables": {},
            "input": {},
            "nodes": {
                "gen": {
                    "type": "image_generation",
                    "output": {"source": "generated", "mime": "image/jpeg", "filename": "image.jpg", "path": picture},
                }
            },
        },
    )
    assert uploaded[-1][1] == "/pics/cat.jpg"
    with open(uploaded[-1][0], "rb") as handle:
        assert handle.read().startswith(b"\xff\xd8\xff")


@pytest.mark.asyncio
async def test_yandex_disk_error_hides_token() -> None:
    class Boom:
        def __init__(self, token: str):
            self.token = token

        async def __aenter__(self):
            raise RuntimeError(f"auth failed {self.token}")

        async def __aexit__(self, *_args):
            return False

    with pytest.raises(ValueError, match="Яндекс Диск") as raised:
        await YandexDiskAction(client_factory=Boom).execute(
            YandexDiskNode(id="disk", operation="download", token="secret-token", remote_path="/a.jpg"),
            {"input": {}, "variables": {}},
        )
    assert "secret-token" not in str(raised.value)


def test_image_recognition_requires_image_parent() -> None:
    wrong = WorkflowGraph(nodes=[
        PromptNode(id="prompt", prompt="text", children=["vision"]),
        ImageRecognitionNode(id="vision", prompt="что тут?", parents=["prompt"]),
    ])
    errors = validate_graph(wrong, strict=True)
    assert any("сразу после узла «Изображение»" in item for item in errors)

    ok = WorkflowGraph(nodes=[
        ImageNode(id="img", source="url", url="https://example.com/a.jpg", children=["vision"]),
        ImageRecognitionNode(id="vision", prompt="что тут?", parents=["img"]),
    ])
    assert validate_graph(ok, strict=True) == []
    assert NodeType.IMAGE_RECOGNITION in NodeType.single_incoming()
