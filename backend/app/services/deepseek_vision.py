"""Распознавание картинки через DeepSeek Vision.

Документация: https://api-docs.deepseek.com/guides/vision/
Картинка уходит как image_url с data URL (base64) в chat/completions.
"""

from __future__ import annotations

import base64

import httpx

from core.config import settings

_SUPPORTED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class DeepSeekVisionProvider:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def recognize_image(self, prompt: str, data: bytes, mime: str, filename: str) -> str:
        key = (settings.deepseek_api_key or "").strip()
        if not key:
            raise ValueError("Распознавание изображений не настроено")
        safe_mime = mime if mime in _SUPPORTED_MIME else "image/jpeg"
        encoded = base64.b64encode(data).decode("ascii")
        payload = {
            "model": settings.deepseek_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{safe_mime};base64,{encoded}"},
                        },
                    ],
                }
            ],
        }
        if self._client is not None:
            return await self._complete(self._client, key, payload)
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            return await self._complete(client, key, payload)

    async def _complete(self, client: httpx.AsyncClient, key: str, payload: dict) -> str:
        base = settings.deepseek_base_url.rstrip("/")
        response = await client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        if response.status_code >= 400:
            raise ValueError(f"Распознавание изображения вернуло ошибку {response.status_code}")
        body = response.json()
        choices = body.get("choices") if isinstance(body, dict) else None
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Распознавание изображения вернуло пустой ответ")
        return content
