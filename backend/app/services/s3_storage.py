"""Файлы блоков «Изображение», «Файл» и «Расшифровка аудио» хранятся в Yandex Cloud S3."""

from __future__ import annotations

import asyncio
import functools
import os
import uuid

import boto3

from core.config import settings


@functools.lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )


class S3StorageService:
    def __init__(self, client=None, bucket: str | None = None):
        self._client = client or _client()
        self.bucket = bucket or settings.aws_bucket_name

    @staticmethod
    def build_key(user_id: int, filename: str) -> str:
        ext = os.path.splitext(filename or "")[1][:20]
        return f"users/{user_id}/{uuid.uuid4().hex}{ext}"

    async def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        kwargs = {"Bucket": self.bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        await asyncio.to_thread(self._client.put_object, **kwargs)

    async def download_bytes(self, key: str) -> bytes:
        def _get() -> bytes:
            return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

        return await asyncio.to_thread(_get)

    async def delete_objects(self, keys: list[str]) -> None:
        unique = [key for key in dict.fromkeys(keys) if key]
        if not unique:
            return

        def _delete() -> None:
            for i in range(0, len(unique), 1000):
                chunk = unique[i : i + 1000]
                self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": key} for key in chunk]},
                )

        await asyncio.to_thread(_delete)
