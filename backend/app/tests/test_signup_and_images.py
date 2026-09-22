import pytest
from fastapi import HTTPException

from schemas.admin import AdminUserUpdate
from services.email_domains import email_domain_allowed
from services.stored_images import (
    IMAGE_NODE_RATE_LIMIT,
    IMAGE_QUOTA_MESSAGE,
    MAX_USER_IMAGE_BYTES,
    consume_image_node_budget,
    decoded_base64_size,
    strip_stored_images,
    uploaded_images,
)


def test_email_allowlist_accepts_known_domains_only() -> None:
    assert email_domain_allowed("test@gmail.com")
    assert email_domain_allowed("Test@Ya.ru")
    assert email_domain_allowed("a@mail.ru")
    assert not email_domain_allowed("test@10minutes.email")
    assert not email_domain_allowed("test@gmail.com.evil.test")
    assert not email_domain_allowed("not-an-email")


def test_strip_stored_images_clears_only_uploaded_bytes() -> None:
    snapshot = {
        "nodes": [
            {"id": "img", "type": "image", "source": "file", "file_base64": "aGVsbG8=", "filename": "a.png"},
            {"id": "link", "type": "image", "source": "url", "url": "https://example.com/a.png", "file_base64": ""},
            {"id": "search", "type": "web_search"},
        ]
    }
    assert strip_stored_images(snapshot) is True
    assert snapshot["nodes"][0]["file_base64"] == ""
    assert snapshot["nodes"][0]["filename"] == "a.png"
    assert snapshot["nodes"][1]["url"] == "https://example.com/a.png"
    assert strip_stored_images(snapshot) is False


def test_uploaded_images_ignore_links() -> None:
    nodes = [
        {"id": "file", "type": "image", "source": "file", "file_base64": "aGVsbG8="},
        {"id": "url", "type": "image", "source": "url", "url": "https://example.com/a.png"},
    ]
    assert uploaded_images(nodes) == [("file", decoded_base64_size("aGVsbG8="))]
    assert decoded_base64_size("aGVsbG8=") == len(b"hello")


def test_empty_plan_grant_is_not_a_purchase() -> None:
    update = AdminUserUpdate(grant_plan_id=0, request_id="request-1")
    assert update.grant_plan_id is None
    update = AdminUserUpdate(grant_plan_id="", request_id="request-1")
    assert update.grant_plan_id is None
    update = AdminUserUpdate(grant_plan_id=4, request_id="request-1")
    assert update.grant_plan_id == 4


class _Redis:
    def __init__(self) -> None:
        self.value = 0
        self.ttl = None

    async def incrby(self, key: str, amount: int) -> int:
        self.value += amount
        return self.value

    async def decrby(self, key: str, amount: int) -> int:
        self.value -= amount
        return self.value

    async def expire(self, key: str, ttl: int) -> None:
        self.ttl = ttl


@pytest.mark.asyncio
async def test_image_node_rate_limit_rolls_back_the_overflow() -> None:
    redis = _Redis()
    await consume_image_node_budget(redis, 7, 60)
    assert redis.value == 60
    assert redis.ttl == 60
    with pytest.raises(HTTPException) as caught:
        await consume_image_node_budget(redis, 7, 1)
    assert caught.value.status_code == 429
    assert redis.value == 60
    assert IMAGE_NODE_RATE_LIMIT == 60
    assert MAX_USER_IMAGE_BYTES == 100 * 1024 * 1024
    assert "100 МБ" in IMAGE_QUOTA_MESSAGE
