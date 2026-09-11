import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from core.config import settings
from deps.admin import require_admin


def test_admin_credentials_from_environment(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_login", "root")
    monkeypatch.setattr(settings, "admin_password", "secret")
    assert require_admin(HTTPBasicCredentials(username="root", password="secret")) == "root"


def test_admin_rejects_invalid_password(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_login", "root")
    monkeypatch.setattr(settings, "admin_password", "secret")
    with pytest.raises(HTTPException) as error:
        require_admin(HTTPBasicCredentials(username="root", password="wrong"))
    assert error.value.status_code == 401
