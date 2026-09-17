import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from services.auth import AuthService


class FakeRedis:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.store: dict[str, str] = {}
        self.incr_counts: dict[str, int] = {}

    async def getdel(self, key: str) -> str | None:
        return self.value

    async def get(self, key: str) -> str | None:
        if key in self.store:
            return self.store[key]
        return self.value

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool | None = None) -> bool:
        self.store[key] = value
        self.value = value
        return True

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.value = None

    async def incr(self, key: str) -> int:
        self.incr_counts[key] = self.incr_counts.get(key, 0) + 1
        return self.incr_counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None


class FakeScalar:
    def __init__(self, value=None) -> None:
        self.value = value

    async def scalar(self, _query) -> object:
        return self.value

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_consume_telegram_code_json() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(json.dumps({"chat_id": 42, "name": "Ada"})))
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 42
    assert name == "Ada"
    assert purpose == "login"


@pytest.mark.asyncio
async def test_consume_telegram_code_link_purpose() -> None:
    service = AuthService(
        db=SimpleNamespace(),
        redis_client=FakeRedis(json.dumps({"chat_id": 42, "name": "Ada", "purpose": "link"})),
    )
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 42
    assert name == "Ada"
    assert purpose == "link"


@pytest.mark.asyncio
async def test_consume_telegram_code_legacy_plain() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis("99"))
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 99
    assert name == "Telegram"
    assert purpose == "login"


@pytest.mark.asyncio
async def test_consume_telegram_code_rejects_missing() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(None))
    with pytest.raises(HTTPException) as error:
        await service._consume_telegram_code("ABC123")
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_request_email_link_sends_code() -> None:
    redis = FakeRedis()
    mail = SimpleNamespace(send=AsyncMock())
    user = SimpleNamespace(id=7, name="Ada", email=None, identities=[])
    service = AuthService(db=FakeScalar(), redis_client=redis, email_provider=mail)
    await service.request_email_link(user, "ada@example.com")
    mail.send.assert_awaited()
    stored = json.loads(redis.store["email_link_pending:7"])
    assert stored["email"] == "ada@example.com"
    assert stored["code_hash"]


@pytest.mark.asyncio
async def test_request_email_link_rejects_same_email() -> None:
    user = SimpleNamespace(id=7, name="Ada", email="ada@example.com", identities=[])
    service = AuthService(db=FakeScalar(), redis_client=FakeRedis(), email_provider=SimpleNamespace(send=AsyncMock()))
    with pytest.raises(HTTPException) as error:
        await service.request_email_link(user, "ada@example.com")
    assert error.value.status_code == 400



@pytest.mark.asyncio
async def test_consume_telegram_code_json() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(json.dumps({"chat_id": 42, "name": "Ada"})))
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 42
    assert name == "Ada"
    assert purpose == "login"


@pytest.mark.asyncio
async def test_consume_telegram_code_link_purpose() -> None:
    service = AuthService(
        db=SimpleNamespace(),
        redis_client=FakeRedis(json.dumps({"chat_id": 42, "name": "Ada", "purpose": "link"})),
    )
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 42
    assert name == "Ada"
    assert purpose == "link"


@pytest.mark.asyncio
async def test_consume_telegram_code_legacy_plain() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis("99"))
    chat_id, name, purpose = await service._consume_telegram_code("ABC123")
    assert chat_id == 99
    assert name == "Telegram"
    assert purpose == "login"


@pytest.mark.asyncio
async def test_consume_telegram_code_rejects_missing() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(None))
    with pytest.raises(HTTPException) as error:
        await service._consume_telegram_code("ABC123")
    assert error.value.status_code == 401
