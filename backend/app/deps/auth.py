from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import helper
from deps.database import get_db
from models.user import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials:
        raise HTTPException(401, "Требуется авторизация")
    payload = helper.verify_token(credentials.credentials)
    user = await db.scalar(
        select(User).options(selectinload(User.identities)).where(User.id == int(payload["sub"]))
    )
    if not user or not user.is_active:
        raise HTTPException(401, "Пользователь недоступен")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    if not credentials:
        return None
    try:
        payload = helper.verify_token(credentials.credentials)
    except HTTPException:
        return None
    user = await db.scalar(
        select(User).options(selectinload(User.identities)).where(User.id == int(payload["sub"]))
    )
    if not user or not user.is_active:
        return None
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def ensure_owner(owner_id: int, user: User) -> None:
    if owner_id != user.id:
        raise HTTPException(404, "Объект не найден")
