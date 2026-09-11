import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import settings

basic = HTTPBasic(auto_error=False)


def require_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
) -> str:
    if not settings.admin_login or not settings.admin_password:
        raise HTTPException(503, "Админ-доступ не настроен")
    valid = bool(
        credentials
        and secrets.compare_digest(credentials.username, settings.admin_login)
        and secrets.compare_digest(credentials.password, settings.admin_password)
    )
    if not valid:
        raise HTTPException(401, "Неверный логин или пароль", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


AdminActor = Annotated[str, Depends(require_admin)]
