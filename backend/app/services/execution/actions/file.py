from __future__ import annotations

import base64
import binascii
import os

from schemas.workflow import FileNode
from services.execution.actions.base import NodeAction
from services.media_files import guess_mime, write_temp_bytes

TEXT_PREVIEW_BYTES = 200_000
TEXT_EXTENSIONS = frozenset({".txt", ".csv", ".tsv", ".json", ".md", ".xml", ".html", ".htm", ".yaml", ".yml", ".log"})


def _is_text(filename: str, mime: str) -> bool:
    if mime.startswith("text/") or mime in {"application/json", "application/xml"}:
        return True
    return os.path.splitext(filename)[1].lower() in TEXT_EXTENSIONS


def _decode_text(data: bytes) -> str | None:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


class FileAction(NodeAction):
    async def execute(self, node: FileNode, context: dict) -> dict:
        encoded = (node.file_base64 or "").strip()
        if not encoded:
            raise ValueError("Файл: загрузите файл")
        try:
            data = base64.b64decode(encoded.split(",")[-1], validate=False)
        except (binascii.Error, ValueError):
            raise ValueError("Файл: некорректные данные файла") from None
        filename = os.path.basename((node.filename or "").strip()) or "file"
        mime = guess_mime(filename, "application/octet-stream")
        path = write_temp_bytes(data, os.path.splitext(filename)[1])
        output: dict = {
            "source": "file",
            "filename": filename,
            "mime": mime,
            "size": len(data),
            "path": path,
        }
        if _is_text(filename, mime) and len(data) <= TEXT_PREVIEW_BYTES:
            text = _decode_text(data)
            if text is not None:
                output["text"] = text
        return output
