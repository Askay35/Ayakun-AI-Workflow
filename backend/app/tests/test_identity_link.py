import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.auth import AuthService


class FakeRedis:
    def __init__(self, value: str | None) -> None:
        self.value = value

    async def getdel(self, key: str) -> str | None:
        return self.value


@pytest.mark.asyncio
async def test_consume_telegram_code_json() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(json.dumps({"chat_id": 42, "name": "Ada"})))
    chat_id, name = await service._consume_telegram_code("ABC123")
    assert chat_id == 42
    assert name == "Ada"


@pytest.mark.asyncio
async def test_consume_telegram_code_legacy_plain() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis("99"))
    chat_id, name = await service._consume_telegram_code("ABC123")
    assert chat_id == 99
    assert name == "Telegram"


@pytest.mark.asyncio
async def test_consume_telegram_code_rejects_missing() -> None:
    service = AuthService(db=SimpleNamespace(), redis_client=FakeRedis(None))
    with pytest.raises(HTTPException) as error:
        await service._consume_telegram_code("ABC123")
    assert error.value.status_code == 401
