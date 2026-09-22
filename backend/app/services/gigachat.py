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
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Protocol

import httpx

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
# Генерация картинок в гайде Sber идёт моделью GigaChat + function_call=auto.
IMAGE_MODEL = "GigaChat"
# example_vision.ipynb: vision-модель и attachments без function_call.
VISION_MODEL = "GigaChat-2-Max"
# Гайд «Работа с файлами»: аудио через attachments и function_call=auto.
AUDIO_MODEL = "GigaChat"

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
            raise ValueError(f"Не удалось загрузить файл ({response.status_code})")
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
        # Загрузка файла и chat.attachments — как в гайде по файлам и example_vision.ipynb.
        # Для vision function_call не передаём (ноутбук). Для аудио — "auto" (гайд).
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
        return await self._chat_with_file(
            prompt,
            data,
            mime,
            filename,
            model=AUDIO_MODEL,
            function_call="auto",
        )
