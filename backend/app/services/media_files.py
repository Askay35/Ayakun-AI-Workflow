"""Канонический payload изображения и чтение байтов для следующих узлов.

Форма, которую читают распознавание и Яндекс Диск:

    {
      "source": "url" | "file" | "generated" | "yandex",
      "mime": "image/jpeg",
      "filename": "...",          # optional
      "url": "https://...",       # optional
      "path": "/tmp/ayakun-...",  # preferred: файл на диске воркера
      "base64": "..."             # только если path нет
    }
"""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
import wave
from math import ceil

import httpx

IMAGE_SOURCES = frozenset({"url", "file", "generated", "yandex"})


def write_temp_bytes(data: bytes, suffix: str) -> str:
    handle, path = tempfile.mkstemp(prefix="ayakun-", suffix=suffix or "")
    try:
        os.write(handle, data)
    finally:
        os.close(handle)
    return path


def guess_mime(filename: str, fallback: str) -> str:
    guessed, _encoding = mimetypes.guess_type(filename or "")
    return guessed or fallback


def image_payload(
    *,
    source: str,
    mime: str,
    filename: str | None = None,
    url: str | None = None,
    path: str | None = None,
    base64_data: str | None = None,
) -> dict:
    if source not in IMAGE_SOURCES:
        raise ValueError("Изображение: неизвестный источник")
    payload: dict = {"source": source, "mime": mime or "application/octet-stream"}
    if filename:
        payload["filename"] = filename
    if url:
        payload["url"] = url
    if path:
        payload["path"] = path
    elif base64_data:
        payload["base64"] = base64_data
    return payload


def normalize_image_output(output: object) -> dict:
    if not isinstance(output, dict):
        raise ValueError("Изображение: предыдущий узел не вернул файл")
    source = output.get("source")
    if source not in IMAGE_SOURCES:
        if output.get("path"):
            source = "file"
        elif output.get("url"):
            source = "url"
        elif output.get("base64"):
            source = "file"
        else:
            raise ValueError("Изображение: нет файла, ссылки или данных предыдущего узла")
    filename = output.get("filename") if isinstance(output.get("filename"), str) else None
    mime = output.get("mime") if isinstance(output.get("mime"), str) and output.get("mime") else guess_mime(filename or "", "image/jpeg")
    return image_payload(
        source=str(source),
        mime=mime,
        filename=filename,
        url=output.get("url") if isinstance(output.get("url"), str) else None,
        path=output.get("path") if isinstance(output.get("path"), str) else None,
        base64_data=output.get("base64") if isinstance(output.get("base64"), str) else None,
    )


def _read_path(path: str) -> bytes:
    if not path or not os.path.isfile(path):
        raise ValueError("Файл предыдущего узла не найден")
    with open(path, "rb") as handle:
        return handle.read()


async def load_binary(payload: dict, client: httpx.AsyncClient) -> tuple[bytes, str, str]:
    filename = str(payload.get("filename") or "file")
    mime = str(payload.get("mime") or guess_mime(filename, "application/octet-stream"))
    path = payload.get("path")
    if isinstance(path, str) and path:
        return _read_path(path), mime, filename
    encoded = payload.get("base64")
    if isinstance(encoded, str) and encoded.strip():
        try:
            return base64.b64decode(encoded), mime, filename
        except (ValueError, TypeError) as exc:
            raise ValueError("Некорректные данные файла") from exc
    url = payload.get("url")
    if isinstance(url, str) and url.strip():
        response = await client.get(url)
        if response.status_code >= 400 or not response.content:
            raise ValueError(f"Не удалось скачать файл ({response.status_code})")
        header = response.headers.get("content-type", "")
        if header:
            mime = header.split(";", 1)[0].strip() or mime
        return response.content, mime, filename
    raise ValueError("Нет файла для обработки")


def audio_duration_seconds(data: bytes, filename: str) -> float | None:
    """Длительность, если контейнер читается стандартной библиотекой. Иначе None → 1 минута в тарифе."""
    name = (filename or "").lower()
    if not name.endswith(".wav") and not data.startswith(b"RIFF"):
        return None
    try:
        import io

        with wave.open(io.BytesIO(data), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return frames / float(rate)
    except (wave.Error, EOFError, OSError):
        return None


def billed_audio_minutes(duration_seconds: object) -> int:
    """Минимум 1 минута, иначе ceil(секунды / 60)."""
    if duration_seconds is None:
        return 1
    try:
        seconds = float(duration_seconds)
    except (TypeError, ValueError):
        return 1
    if seconds <= 0:
        return 1
    return max(1, ceil(seconds / 60))
