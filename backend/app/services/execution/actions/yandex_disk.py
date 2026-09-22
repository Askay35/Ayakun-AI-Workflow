from __future__ import annotations

import os
import tempfile

from helper import render_template
from schemas.workflow import YandexDiskNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload, parent_records
from services.media_files import file_output, guess_mime, image_payload, load_binary, write_temp_bytes


def _redact(message: str, token: str) -> str:
    if token and token in message:
        return message.replace(token, "***")
    return message


class YandexDiskAction(NodeAction):
    def __init__(self, client_factory=None):
        self._client_factory = client_factory

    def _open(self, token: str):
        if self._client_factory is not None:
            return self._client_factory(token)
        import yadisk

        return yadisk.AsyncClient(token=token)

    async def execute(self, node: YandexDiskNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        token = render_template(node.token or "", payload, variables).strip()
        remote = render_template(node.remote_path or "", payload, variables).strip()
        if not token:
            raise ValueError("Яндекс Диск: укажите токен")
        if not remote:
            raise ValueError("Яндекс Диск: укажите путь")
        try:
            async with self._open(token) as client:
                if node.operation == "download":
                    return await self._download(client, remote)
                return await self._upload(node, client, remote, payload, variables, context)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Яндекс Диск: {_redact(str(exc), token)}") from None

    async def _download(self, client, remote: str) -> dict:
        suffix = os.path.splitext(remote)[1] or ""
        handle, path = tempfile.mkstemp(prefix="ayakun-yd-", suffix=suffix)
        os.close(handle)
        await client.download(remote, path)
        filename = os.path.basename(remote) or "file"
        mime = guess_mime(filename, "application/octet-stream")
        size = os.path.getsize(path)
        body = {
            "source": "yandex",
            "remote_path": remote,
            "path": path,
            "filename": filename,
            "mime": mime,
            "size": size,
        }
        if mime.startswith("image/"):
            body.update(image_payload(source="yandex", mime=mime, filename=filename, path=path))
            body["remote_path"] = remote
            body["size"] = size
        return body

    async def _upload(self, node: YandexDiskNode, client, remote: str, payload, variables, context) -> dict:
        records = parent_records(node, context)
        parent = records[0].get("output") if records else None
        incoming = file_output(parent)
        content = render_template(node.content or "", payload, variables)
        upload_path = ""
        if incoming is not None:
            import httpx

            async with httpx.AsyncClient(timeout=60) as http:
                data, _mime, filename = await load_binary(incoming, http)
            upload_path = write_temp_bytes(data, os.path.splitext(filename)[1] or os.path.splitext(remote)[1] or "")
        elif content.strip():
            upload_path = write_temp_bytes(content.encode("utf-8"), os.path.splitext(remote)[1] or ".txt")
        if not upload_path:
            raise ValueError("Яндекс Диск: нечего загружать — подключите файл или напишите текст")
        await client.upload(upload_path, remote)
        return {"uploaded": True, "remote_path": remote, "source": "yandex"}
