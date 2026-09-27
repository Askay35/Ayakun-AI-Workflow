"""Промокоды: скидка в процентах на подключение тарифа, одно использование на пользователя."""

from __future__ import annotations

import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Plan, PromoCode, PromoCodeRedemption

PROMO_NOT_FOUND = "Промокод не найден или недействителен"
PROMO_EXPIRED = "Срок действия промокода истёк"
PROMO_WRONG_PLAN = "Промокод не действует для этого тарифа"
PROMO_ALREADY_USED = "Этот промокод уже был использован на вашем аккаунте"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class PromoCodeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find(self, code: str) -> PromoCode | None:
        normalized = code.strip()
        if not normalized:
            return None
        return await self.db.scalar(select(PromoCode).where(func.upper(PromoCode.code) == normalized.upper()))

    def applies_to(self, promo: PromoCode, plan: Plan) -> bool:
        return not promo.plan_ids or plan.id in promo.plan_ids

    def is_expired(self, promo: PromoCode, now: datetime.datetime | None = None) -> bool:
        return bool(promo.expires_at and promo.expires_at < (now or _now()))

    async def already_redeemed(self, promo_id: int, user_id: int) -> bool:
        return bool(await self.db.scalar(
            select(PromoCodeRedemption.id).where(
                PromoCodeRedemption.promo_code_id == promo_id,
                PromoCodeRedemption.user_id == user_id,
            )
        ))

    async def resolve(self, code: str, plan: Plan, user_id: int) -> PromoCode:
        """Проверяет код и бросает HTTPException(422, ...) с понятной причиной, если применить нельзя."""
        promo = await self.find(code)
        if promo is None or not promo.active:
            raise HTTPException(422, PROMO_NOT_FOUND)
        if self.is_expired(promo):
            raise HTTPException(422, PROMO_EXPIRED)
        if not self.applies_to(promo, plan):
            raise HTTPException(422, PROMO_WRONG_PLAN)
        if await self.already_redeemed(promo.id, user_id):
            raise HTTPException(422, PROMO_ALREADY_USED)
        return promo

    async def usage_counts(self, promo_ids: list[int]) -> dict[int, int]:
        if not promo_ids:
            return {}
        rows = await self.db.execute(
            select(PromoCodeRedemption.promo_code_id, func.count(PromoCodeRedemption.id))
            .where(PromoCodeRedemption.promo_code_id.in_(promo_ids))
            .group_by(PromoCodeRedemption.promo_code_id)
        )
        return {promo_id: count for promo_id, count in rows.all()}
