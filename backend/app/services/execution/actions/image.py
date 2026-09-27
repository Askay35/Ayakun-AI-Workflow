import base64
import os

import httpx

from helper import render_template
from schemas.workflow import ImageNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload, parent_records
from services.media_files import guess_mime, image_payload, normalize_image_output, write_temp_bytes
from services.s3_storage import S3StorageService


class ImageAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient | None = None, storage: S3StorageService | None = None):
        self.client = client
        self.storage = storage

    async def execute(self, node: ImageNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        if node.source == "upstream":
            records = parent_records(node, context)
            if len(records) != 1:
                raise ValueError("Изображение: нужна ровно одна входящая связь")
            return normalize_image_output(records[0].get("output"))
        if node.source == "file":
            if node.s3_key and self.storage is not None:
                data = await self.storage.download_bytes(node.s3_key)
            else:
                encoded = (node.file_base64 or "").strip()
                if not encoded:
                    raise ValueError("Изображение: загрузите файл")
                try:
                    data = base64.b64decode(encoded)
                except (ValueError, TypeError) as exc:
                    raise ValueError("Изображение: некорректный файл") from exc
            filename = (node.filename or "image").strip() or "image"
            suffix = os.path.splitext(filename)[1] or ".img"
            path = write_temp_bytes(data, suffix)
            return image_payload(
                source="file",
                mime=guess_mime(filename, "image/jpeg"),
                filename=filename,
                path=path,
            )
        url = render_template(node.url or "", payload, variables).strip()
        if not url:
            raise ValueError("Изображение: укажите ссылку")
        filename = (node.filename or "").strip() or os.path.basename(url.split("?", 1)[0]) or "image"
        return image_payload(
            source="url",
            mime=guess_mime(filename, "image/jpeg"),
            filename=filename,
            url=url,
        )
