import base64
import os

import httpx

from helper import render_template
from schemas.workflow import AudioTranscriptionNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload, parent_records
from services.gigachat import AUDIO_TRANSCRIPT_PROMPT, GigaChatMediaProvider, MediaModelProvider
from services.media_files import audio_duration_seconds, billed_audio_minutes, guess_mime, load_binary
from services.s3_storage import S3StorageService


class AudioTranscriptionAction(NodeAction):
    def __init__(
        self,
        media: MediaModelProvider | None = None,
        client: httpx.AsyncClient | None = None,
        storage: S3StorageService | None = None,
    ):
        self.media = media or GigaChatMediaProvider()
        self.client = client
        self.storage = storage

    async def execute(self, node: AudioTranscriptionNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        data, mime, filename = await self._bytes(node, payload, variables, context)
        prompt = render_template(node.prompt or "", payload, variables).strip() or AUDIO_TRANSCRIPT_PROMPT
        text = await self.media.transcribe_audio(prompt, data, mime, filename)
        duration = audio_duration_seconds(data, filename)
        minutes = billed_audio_minutes(duration)
        return {
            "text": text.strip(),
            "duration_seconds": duration,
            "duration_minutes": minutes,
        }

    async def _bytes(self, node: AudioTranscriptionNode, payload, variables, context) -> tuple[bytes, str, str]:
        if node.source == "upstream":
            records = parent_records(node, context)
            parent = records[0].get("output") if len(records) == 1 else None
            if not isinstance(parent, dict):
                raise ValueError("Расшифровка аудио: предыдущий узел не вернул файл")
            return await self._load(parent)
        if node.source == "file":
            if node.s3_key and self.storage is not None:
                data = await self.storage.download_bytes(node.s3_key)
            else:
                encoded = (node.file_base64 or "").strip()
                if not encoded:
                    raise ValueError("Расшифровка аудио: загрузите файл")
                try:
                    data = base64.b64decode(encoded)
                except (ValueError, TypeError) as exc:
                    raise ValueError("Расшифровка аудио: некорректный файл") from exc
            filename = (node.filename or "audio").strip() or "audio"
            return data, guess_mime(filename, "audio/wav"), filename
        url = render_template(node.url or "", payload, variables).strip()
        if not url:
            raise ValueError("Расшифровка аудио: укажите ссылку")
        filename = (node.filename or "").strip() or os.path.basename(url.split("?", 1)[0]) or "audio"
        return await self._load({"url": url, "filename": filename, "mime": guess_mime(filename, "audio/mpeg")})

    async def _load(self, payload: dict) -> tuple[bytes, str, str]:
        if self.client is not None:
            return await load_binary(payload, self.client)
        async with httpx.AsyncClient(timeout=60) as client:
            return await load_binary(payload, client)
