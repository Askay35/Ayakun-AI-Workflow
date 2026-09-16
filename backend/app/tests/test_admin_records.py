import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from api.v1 import admin_records as admin_api
from models.billing import Wallet, WalletLedger
from models.user import User
from schemas.admin import AdminPage, AdminUserResponse, AdminUserUpdate
from services.admin_records import _integrity_message
from services.billing.credits import CreditService


class FakeWallets:
    def __init__(self, wallet: Wallet) -> None:
        self.wallet_obj = wallet
        self.keys: set[str] = set()

    async def wallet(self, user: User, *, lock: bool = False) -> Wallet:
        return self.wallet_obj

    async def already_applied(self, key: str) -> bool:
        return key in self.keys


class FakeDB:
    def __init__(self, wallets: FakeWallets) -> None:
        self.wallets = wallets
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, WalletLedger):
            self.wallets.keys.add(obj.idempotency_key)

    async def commit(self) -> None:
        self.commits += 1


def make_user(user_id: int = 7) -> User:
    return User(id=user_id, name="Админ тест", email="admin-test@example.invalid")


def make_wallet(*, balance: str = "100", reserved: str = "0") -> Wallet:
    return Wallet(user_id=7, balance=Decimal(balance), reserved=Decimal(reserved))


def sample_user_response(**overrides: object) -> AdminUserResponse:
    now = datetime.datetime.now(datetime.UTC)
    payload = dict(
        id=1,
        name="Иван",
        email="ivan@example.com",
        chat_id=None,
        email_verified=True,
        is_active=True,
        balance=Decimal("12.5"),
        reserved=Decimal("0"),
        identities=[],
        created_at=now,
        updated_at=now,
    )
    payload.update(overrides)
    return AdminUserResponse(**payload)  # type: ignore[arg-type]


class FakeRecords:
    def __init__(self, user: AdminUserResponse | None = None) -> None:
        self.user = user or sample_user_response()
        self.updated = None
        self.deleted = None

    async def list_users(self, **kwargs):
        return AdminPage(items=[self.user], total=1, page=kwargs.get("page", 1), page_size=kwargs.get("page_size", 20))

    async def get_user(self, user_id: int):
        if user_id != self.user.id:
            raise HTTPException(404, "Пользователь не найден")
        return self.user

    async def update_user(self, user_id: int, data: AdminUserUpdate, actor: str):
        self.updated = (user_id, data, actor)
        return sample_user_response(balance=data.balance or self.user.balance, name=data.name or self.user.name)

    async def delete_user(self, user_id: int, actor: str, request_id: str):
        self.deleted = (user_id, actor, request_id)


@pytest.mark.asyncio
async def test_admin_set_balance_credits_through_ledger() -> None:
    wallet = make_wallet()
    wallets = FakeWallets(wallet)
    db = FakeDB(wallets)
    result = await CreditService(db, wallets).set_balance(  # type: ignore[arg-type]
        make_user(),
        Decimal("150"),
        "admin-balance:req-1",
        actor="root",
        note="компенсация",
    )
    assert result.balance == Decimal("150")
    assert db.commits == 1
    ledger = next(item for item in db.added if isinstance(item, WalletLedger))
    assert ledger.kind.value == "credit"
    assert ledger.amount == Decimal("50")
    assert ledger.idempotency_key == "admin-balance:req-1"
    assert ledger.metadata_["source"] == "admin"
    assert ledger.metadata_["actor"] == "root"
    assert ledger.metadata_["note"] == "компенсация"
    assert ledger.metadata_["previous_balance"] == "100"


@pytest.mark.asyncio
async def test_admin_set_balance_decrease_writes_charge() -> None:
    wallet = make_wallet(balance="80", reserved="10")
    wallets = FakeWallets(wallet)
    db = FakeDB(wallets)
    await CreditService(db, wallets).set_balance(  # type: ignore[arg-type]
        make_user(),
        Decimal("40"),
        "admin-balance:req-2",
        actor="root",
    )
    ledger = next(item for item in db.added if isinstance(item, WalletLedger))
    assert wallet.balance == Decimal("40")
    assert ledger.kind.value == "charge"
    assert ledger.amount == Decimal("-40")


@pytest.mark.asyncio
async def test_admin_set_balance_rejects_below_reserved() -> None:
    wallet = make_wallet(balance="100", reserved="60")
    wallets = FakeWallets(wallet)
    service = CreditService(FakeDB(wallets), wallets)  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as error:
        await service.set_balance(make_user(), Decimal("20"), "admin-balance:req-3", actor="root")
    assert error.value.status_code == 400
    assert "зарезервированной" in error.value.detail


@pytest.mark.asyncio
async def test_admin_set_balance_is_idempotent() -> None:
    wallet = make_wallet()
    wallets = FakeWallets(wallet)
    db = FakeDB(wallets)
    service = CreditService(db, wallets)  # type: ignore[arg-type]
    await service.set_balance(make_user(), Decimal("130"), "admin-balance:same", actor="root")
    await service.set_balance(make_user(), Decimal("999"), "admin-balance:same", actor="root")
    assert wallet.balance == Decimal("130")
    assert sum(1 for item in db.added if isinstance(item, WalletLedger)) == 1


def test_admin_user_response_hides_secrets() -> None:
    payload = sample_user_response().model_dump()
    assert "password_hash" not in payload
    assert "token_hash" not in payload
    assert payload["balance"] == 12.5


def test_admin_user_update_requires_valid_email() -> None:
    with pytest.raises(ValidationError):
        AdminUserUpdate(email="not-an-email", request_id="request-1")
    with pytest.raises(ValidationError):
        AdminUserUpdate(balance=Decimal("-1"), request_id="request-1")


def test_integrity_message_is_russian() -> None:
    class ForeignKeyViolationError(Exception):
        pass

    foreign = IntegrityError("DELETE", {}, ForeignKeyViolationError("fk"))
    assert "Нельзя удалить" in _integrity_message(foreign, deleting=True, entity="пользователя")
    assert "ссылаются" in _integrity_message(foreign, deleting=False, entity="платёж")
    unique = IntegrityError("UPDATE", {}, Exception("duplicate key users_email_key"))
    assert "занят" in _integrity_message(unique, deleting=False, entity="пользователя")


@pytest.mark.asyncio
async def test_admin_user_crud_handlers() -> None:
    service = FakeRecords()
    listed = await admin_api.list_users("root", service, q="иван", is_active=True, page=1, page_size=20)
    assert listed.success is True
    assert listed.data.total == 1
    fetched = await admin_api.get_user(1, "root", service)
    assert fetched.data.email == "ivan@example.com"
    updated = await admin_api.update_user(
        1,
        AdminUserUpdate(balance=Decimal("200"), request_id="request-88"),
        "root",
        service,
    )
    assert updated.data.balance == 200
    assert service.updated[0] == 1
    assert service.updated[2] == "root"
    deleted = await admin_api.delete_user(1, "root", "request-99", service)
    assert deleted.data == {"ok": True}
    assert service.deleted == (1, "root", "request-99")


@pytest.mark.asyncio
async def test_admin_get_user_not_found() -> None:
    with pytest.raises(HTTPException) as error:
        await admin_api.get_user(9, "root", FakeRecords())
    assert error.value.status_code == 404
    assert error.value.detail == "Пользователь не найден"
