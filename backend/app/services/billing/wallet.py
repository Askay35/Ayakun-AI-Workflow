from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.billing import LedgerKind, Plan, UsageRecord, Wallet, WalletLedger
from services.billing.access import user_has_paid_pack
from models.user import User


class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def plans(self) -> list[Plan]:
        return list(await self.db.scalars(select(Plan).order_by(Plan.price)))

    async def run_cap(self, user: User) -> Decimal:
        return Decimal(str(settings.default_run_cap_credits))

    async def ledger(self, user: User) -> list[WalletLedger]:
        return list(await self.db.scalars(
            select(WalletLedger).where(WalletLedger.user_id == user.id).order_by(WalletLedger.created_at.desc())
        ))

    async def usage(self, user: User) -> list[UsageRecord]:
        return list(await self.db.scalars(
            select(UsageRecord).where(UsageRecord.user_id == user.id).order_by(UsageRecord.created_at.desc())
        ))

    async def wallet(self, user: User, *, lock: bool = False) -> Wallet:
        query = select(Wallet).where(Wallet.user_id == user.id)
        wallet = await self.db.scalar(query.with_for_update() if lock else query)
        if not wallet:
            wallet = Wallet(user_id=user.id)
            self.db.add(wallet)
            await self.db.flush()
        return wallet

    async def has_paid_pack(self, user: User) -> bool:
        return await user_has_paid_pack(self.db, user.id)

    async def ensure_initial_credit(self, user: User) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        free_plan = await self.db.scalar(select(Plan).where(Plan.code == "free"))
        initial_credits = Decimal(str(
            free_plan.limits.get("included_credits", settings.initial_token_balance)
            if free_plan else settings.initial_token_balance
        ))
        key = f"initial-credit:{user.id}"
        if not await self.already_applied(key):
            wallet.balance += initial_credits
            self.db.add(WalletLedger(
                user_id=user.id,
                kind=LedgerKind.credit,
                amount=initial_credits,
                idempotency_key=key,
                reference="free-plan",
            ))
        await self.db.commit()
        return wallet

    async def already_applied(self, key: str) -> bool:
        return bool(await self.db.scalar(select(WalletLedger.id).where(WalletLedger.idempotency_key == key)))
