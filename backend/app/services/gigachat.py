"""Клиент медиа-модели. Сейчас это GigaChat; узел в графе провайдера не называет.

Авторизация и файлы — по документации Sber:
- POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth
- POST https://api.giga.chat/v1/chat/completions
- POST https://api.giga.chat/v1/files (purpose=general) и attachments в сообщении
- GET https://api.giga.chat/v1/files/{id}/content
- POST https://api.giga.chat/v1/files/{id}/delete

Сертификат NGW часто не сходится с публичным CA, поэтому verify отключён
только у клиента этого провайдера, не у общего httpx приложения.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Protocol

import httpx
from gigachat import GigaChat
from gigachat.exceptions import GigaChatException, ResponseError

from core.config import settings

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_BASE = "https://api.giga.chat/v1"
SCOPE = "GIGACHAT_API_PERS"
USER_AGENT = "ayakun"
TOKEN_TTL_SECONDS = 30 * 60
# Новый access token удаляет файлы, созданные предыдущим. Они не доживают
# свои 30 минут: обновление токена стирает их сразу. Поэтому файл открываем
# и закрываем на одном токене, а новый токен запрашиваем только когда ни
# одной файловой операции нет. Запас нужен, чтобы не обновлять токен уже
# после загрузки, если до истечения осталось меньше времени, чем длится запрос.
TOKEN_FILE_MARGIN_SECONDS = 5 * 60
# Гайд images-generation всё ещё пишет model=GigaChat, но такого id больше нет:
# 404 — ошибка в названии модели. Актуальный пример «Нарисуй горы» — GigaChat-2-Pro.
IMAGE_MODEL = "GigaChat-2-Pro"
# example_vision.ipynb: vision-модель и attachments без function_call.
VISION_MODEL = "GigaChat-2-Max"
# Имя GigaChat больше не выдаётся. Расшифровка идёт через SDK, модель линейки 2.
AUDIO_MODEL = "GigaChat-2-Pro"
# Хранилище GigaChat принимает только эти аудиоформаты (POST /files).
# Канонический MIME — тот, который уходит в multipart Content-Type.
# https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-file
_AUDIO_UPLOAD = {
    "mp3": ("mp3", "audio/mp3"),
    "wav": ("wav", "audio/wav"),
    "ogg": ("ogg", "audio/x-ogg"),
    "opus": ("opus", "audio/opus"),
    "m4a": ("m4a", "audio/x-m4a"),
    "mp4": ("mp4", "audio/mp4"),
    "weba": ("weba", "audio/webm"),
}
_EXT_FORMAT = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".wave": "wav",
    ".ogg": "ogg",
    ".oga": "ogg",
    ".opus": "opus",
    ".m4a": "m4a",
    ".mp4": "mp4",
    ".weba": "weba",
    ".webm": "weba",
}
# Объявленный тип учитываем, только если байты и расширение ничего не сказали.
# audio/mpeg и audio/ogg в таблице Сбера нет — их переписываем на канонические.
_MIME_FORMAT = {
    "audio/mp3": "mp3",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/x-pn-wav": "wav",
    "audio/x-ogg": "ogg",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/webm": "weba",
}


def _sniff_audio_format(data: bytes) -> str | None:
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"OggS"):
        # .oga у Telegram — тот же контейнер ogg, даже если внутри OpusHead.
        # В таблице GigaChat это формат ogg и Content-Type audio/x-ogg.
        return "ogg"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "weba"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"M4A ", b"M4B ", b"M4P "} or brand.startswith(b"M4A"):
            return "m4a"
        return "mp4"
    return None


def _completion_text(response: object) -> str:
    messages = getattr(response, "messages", None) or []
    for message in messages:
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        for part in content or []:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def gigachat_audio_file(data: bytes, filename: str, mime: str) -> tuple[str, str]:
    """Имя и Content-Type для загрузки: формат файла → MIME из списка GigaChat."""
    name = os.path.basename(filename or "") or "audio"
    ext = os.path.splitext(name)[1].lower()
    sniffed = _sniff_audio_format(data)
    from_ext = _EXT_FORMAT.get(ext)
    declared = (mime or "").split(";", 1)[0].strip().lower()
    from_mime = _MIME_FORMAT.get(declared)
    if sniffed == "mp4" and from_ext == "m4a":
        kind = "m4a"
    elif sniffed:
        kind = sniffed
    elif from_ext:
        kind = from_ext
    elif from_mime:
        kind = from_mime
    else:
        raise ValueError(
            "Аудиоформат не поддерживается. GigaChat принимает mp3, wav, ogg, opus, m4a, mp4 и weba"
        )
    suffix, content_type = _AUDIO_UPLOAD[kind]
    stem = os.path.splitext(name)[0] or "audio"
    return f"{stem}.{suffix}", content_type


AUDIO_TRANSCRIPT_PROMPT = (
    "Расшифруй приложенное аудио. "
    "Сделай максимально близкую к записи стенограмму. "
    "Не сокращай текст, сохрани все слова-паразиты. "
    "Места, которые невозможно разобрать, пометь меткой [неразборчиво]."
)

_IMG_SRC_RE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

_cache_lock = asyncio.Lock()
_files_lock = asyncio.Lock()
_cached_token: str | None = None
_cached_key: str | None = None
_cached_fetched_at: float = 0.0
_open_file_ops = 0


def reset_gigachat_token_cache() -> None:
    global _cached_token, _cached_key, _cached_fetched_at, _open_file_ops
    _cached_token = None
    _cached_key = None
    _cached_fetched_at = 0.0
    _open_file_ops = 0


def parse_generated_image_id(content: str) -> str:
    match = _IMG_SRC_RE.search(content or "")
    if not match or not match.group(1).strip():
        raise ValueError("Генерация изображения: в ответе нет идентификатора файла")
    return match.group(1).strip()


class MediaModelProvider(Protocol):
    async def generate_image(self, prompt: str) -> bytes: ...

    async def recognize_image(self, prompt: str, data: bytes, mime: str, filename: str) -> str: ...

    async def transcribe_audio(self, prompt: str, data: bytes, mime: str, filename: str) -> str: ...


class GigaChatMediaProvider:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    @asynccontextmanager
    async def _session(self):
        if self._client is not None:
            yield self._client
            return
        # verify=False только здесь: цепочка Сбера не проходит публичный CA httpx.
        async with httpx.AsyncClient(verify=False, timeout=180.0, headers={"User-Agent": USER_AGENT}) as client:
            yield client

    @asynccontextmanager
    async def _file_turn(self):
        """Держит один токен на всю операцию и не пускает параллельный OAuth."""
        global _open_file_ops
        async with _files_lock:
            async with self._session() as client:
                token = await self._access_token(client)
                _open_file_ops += 1
                try:
                    yield client, token
                finally:
                    _open_file_ops -= 1

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        global _cached_token, _cached_key, _cached_fetched_at
        key = (settings.gigachat_auth_key or "").strip()
        if not key:
            raise ValueError("Медиа-модель не настроена")
        now = time.monotonic()
        async with _cache_lock:
            age = now - _cached_fetched_at
            fresh = (
                _cached_token
                and _cached_key == key
                and age < TOKEN_TTL_SECONDS - TOKEN_FILE_MARGIN_SECONDS
            )
            if fresh and _cached_token is not None:
                return _cached_token
            if _open_file_ops and _cached_token and _cached_key == key:
                return _cached_token
            token = await self._fetch_token(client, key)
            _cached_token = token
            _cached_key = key
            _cached_fetched_at = time.monotonic()
            return token

    async def _fetch_token(self, client: httpx.AsyncClient, key: str) -> str:
        response = await client.post(
            OAUTH_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {key}",
                "User-Agent": USER_AGENT,
            },
            content=f"scope={SCOPE}",
        )
        if response.status_code >= 400:
            raise ValueError(f"Медиа-модель не выдала токен ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError("Медиа-модель не выдала токен")
        return token

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    async def _chat(self, client: httpx.AsyncClient, token: str, payload: dict) -> str:
        response = await client.post(
            f"{API_BASE}/chat/completions",
            headers=self._auth_headers(token),
            json=payload,
        )
        if response.status_code >= 400:
            raise ValueError(f"Медиа-модель вернула ошибку {response.status_code}")
        body = response.json()
        choices = body.get("choices") if isinstance(body, dict) else None
        if not choices:
            raise ValueError("Медиа-модель вернула пустой ответ")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Медиа-модель вернула пустой ответ")
        return content

    async def _upload(self, client: httpx.AsyncClient, token: str, data: bytes, mime: str, filename: str) -> str:
        response = await client.post(
            f"{API_BASE}/files",
            headers=self._auth_headers(token),
            data={"purpose": "general"},
            files={"file": (filename or "file", data, mime or "application/octet-stream")},
        )
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("message") or "")[:200]
            except Exception:
                detail = ""
            suffix = f": {detail}" if detail else ""
            raise ValueError(f"Не удалось загрузить файл ({response.status_code}){suffix}")
        body = response.json()
        file_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("Хранилище файлов не вернуло идентификатор")
        return file_id

    async def _delete(self, client: httpx.AsyncClient, token: str, file_id: str) -> None:
        await client.post(
            f"{API_BASE}/files/{file_id}/delete",
            headers=self._auth_headers(token),
        )

    async def generate_image(self, prompt: str) -> bytes:
        async with self._file_turn() as (client, token):
            content = await self._chat(
                client,
                token,
                {
                    "model": IMAGE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "function_call": "auto",
                    "functions": [{"name": "text2image"}],
                },
            )
            file_id = parse_generated_image_id(content)
            downloaded = await client.get(
                f"{API_BASE}/files/{file_id}/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/jpg",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                if downloaded.status_code >= 400 or not downloaded.content:
                    raise ValueError(f"Не удалось скачать изображение ({downloaded.status_code})")
                return downloaded.content
            finally:
                await self._delete(client, token, file_id)

    async def _chat_with_file(
        self,
        prompt: str,
        data: bytes,
        mime: str,
        filename: str,
        *,
        model: str,
        function_call: str | None,
    ) -> str:
        # Распознавание: id файла в messages[].attachments, без function_call.
        async with self._file_turn() as (client, token):
            file_id = await self._upload(client, token, data, mime, filename)
            message: dict = {
                "role": "user",
                "content": prompt,
                "attachments": [file_id],
            }
            payload: dict = {"model": model, "messages": [message]}
            if function_call:
                payload["function_call"] = function_call
            try:
                return await self._chat(client, token, payload)
            finally:
                await self._delete(client, token, file_id)

    async def recognize_image(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
        return await self._chat_with_file(
            prompt,
            data,
            mime,
            filename,
            model=VISION_MODEL,
            function_call=None,
        )

    async def transcribe_audio(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
        text = (prompt or "").strip() or AUDIO_TRANSCRIPT_PROMPT
        upload_name, upload_mime = gigachat_audio_file(data, filename, mime)
        key = (settings.gigachat_auth_key or "").strip()
        if not key:
            raise ValueError("Медиа-модель не настроена")
        try:
            async with GigaChat(
                credentials=key,
                scope=SCOPE,
                verify_ssl_certs=False,
                model=AUDIO_MODEL,
                timeout=180.0,
            ) as client:
                uploaded = await client.aupload_file((upload_name, data, upload_mime), purpose="general")
                file_id = uploaded.id_
                if not file_id:
                    raise ValueError("Хранилище файлов не вернуло идентификатор")
                # В gigachat 0.2.3 нет chat.completions и files.upload.
                # Тот же шаг: id файла в content сообщения, текст — в parts[].text.
                response = await client.achat.create(
                    {
                        "model": AUDIO_MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"text": text},
                                    {"files": [{"id": file_id}]},
                                ],
                            }
                        ],
                    }
                )
        except ResponseError as exc:
            detail = (exc.content or b"").decode("utf-8", "replace")[:200]
            suffix = f": {detail}" if detail else ""
            raise ValueError(f"Медиа-модель вернула ошибку {exc.status_code}{suffix}") from exc
        except GigaChatException as exc:
            raise ValueError("Медиа-модель не ответила") from exc
        transcript = _completion_text(response)
        if not transcript:
            raise ValueError("Медиа-модель вернула пустой ответ")
        return transcript
