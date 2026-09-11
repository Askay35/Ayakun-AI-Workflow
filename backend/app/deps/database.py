from collections.abc import AsyncGenerator
from fastapi import Request
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis