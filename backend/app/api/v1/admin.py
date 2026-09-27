from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps.admin import AdminActor
from deps.database import get_db
from models.billing import BillingAudit, Plan, PricingRate, PromoCode, RuntimeSetting
from schemas.admin import AdminStatsResponse
from schemas.billing import (
    AdminPlanUpdate,
    PlanResponse,
    PricingRateResponse,
    PricingRateUpdate,
    PromoCodeCreate,
    PromoCodeResponse,
    PromoCodeUpdate,
    RuntimeSettingUpdate,
)
from schemas.common import ApiResponse
from services.admin_stats import AdminStatsService, Granularity
from services.billing.promo_codes import PromoCodeService
from services.media_settings import normalize_runtime_value

router = APIRouter()


@router.get("/config", response_model=ApiResponse[dict])
async def config(actor: AdminActor, db: AsyncSession = Depends(get_db)):
    rates = list(await db.scalars(
        select(PricingRate)
        .where(PricingRate.provider == "serper")
        .order_by(PricingRate.model)
    ))
    plans = list(await db.scalars(select(Plan).order_by(Plan.price)))
    settings = list(await db.scalars(select(RuntimeSetting).order_by(RuntimeSetting.key)))
    return ApiResponse(success=True, data={
        "pricing": [PricingRateResponse.model_validate(item).model_dump(mode="json") for item in rates],
        "plans": [PlanResponse.model_validate(item).model_dump(mode="json") for item in plans],
        "settings": [
            {"key": item.key, "value": item.value, "description": item.description}
            for item in settings
        ],
    })


@router.get("/stats", response_model=ApiResponse[AdminStatsResponse])
async def stats(
    actor: AdminActor,
    granularity: Granularity = "day",
    points: int = Query(30, ge=2, le=120),
    timezone: str = Query("Europe/Moscow", max_length=64),
    db: AsyncSession = Depends(get_db),
):
    return ApiResponse(success=True, data=await AdminStatsService(db).stats(granularity, points, timezone))


@router.put("/pricing/{rate_id}", response_model=ApiResponse[PricingRateResponse])
async def update_pricing(
    rate_id: int,
    data: PricingRateUpdate,
    actor: AdminActor,
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == data.request_id)):
        rate = await db.get(PricingRate, rate_id)
        if not rate or rate.provider != "serper":
            raise HTTPException(404, "Тариф поиска не найден")
        return ApiResponse(success=True, data=rate)
    rate = await db.get(PricingRate, rate_id, with_for_update=True)
    if not rate or rate.provider != "serper":
        raise HTTPException(404, "Тариф поиска не найден")
    before = PricingRateResponse.model_validate(rate).model_dump(mode="json")
    rate.search_credits = data.search_credits
    rate.active = data.active
    after = PricingRateResponse.model_validate(rate).model_dump(mode="json")
    db.add(BillingAudit(
        actor=actor,
        action="update",
        entity_type="pricing_rate",
        entity_id=str(rate.id),
        before=before,
        after=after,
        request_id=data.request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data=rate)


@router.put("/plans/{plan_id}", response_model=ApiResponse[PlanResponse])
async def update_plan(
    plan_id: int,
    data: AdminPlanUpdate,
    actor: AdminActor,
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == data.request_id)):
        plan = await db.get(Plan, plan_id)
        if not plan:
            raise HTTPException(404, "Тариф не найден")
        return ApiResponse(success=True, data=plan)
    plan = await db.get(Plan, plan_id, with_for_update=True)
    if not plan:
        raise HTTPException(404, "Тариф не найден")
    before = PlanResponse.model_validate(plan).model_dump(mode="json")
    plan.name = data.name
    plan.price = data.price
    plan.currency = data.currency.upper()
    limits = {
        **(plan.limits or {}),
        "included_credits": float(data.included_credits),
        "run_cap_credits": float(data.run_cap_credits),
    }
    if data.max_files is not None:
        limits["max_files"] = data.max_files
    if data.max_storage_mb is not None:
        limits["max_storage_mb"] = data.max_storage_mb
    plan.limits = limits
    after = PlanResponse.model_validate(plan).model_dump(mode="json")
    db.add(BillingAudit(
        actor=actor,
        action="update",
        entity_type="plan",
        entity_id=str(plan.id),
        before=before,
        after=after,
        request_id=data.request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data=plan)


@router.put("/settings/{key}", response_model=ApiResponse[dict])
async def update_setting(
    key: str,
    data: RuntimeSettingUpdate,
    actor: AdminActor,
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == data.request_id)):
        setting = await db.get(RuntimeSetting, key)
        if not setting:
            raise HTTPException(404, "Настройка не найдена")
        return ApiResponse(success=True, data={
            "key": setting.key, "value": setting.value, "description": setting.description
        })
    setting = await db.get(RuntimeSetting, key, with_for_update=True)
    if not setting:
        raise HTTPException(404, "Настройка не найдена")
    before = {"value": setting.value}
    try:
        setting.value = normalize_runtime_value(key, data.value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(BillingAudit(
        actor=actor,
        action="update",
        entity_type="runtime_setting",
        entity_id=key,
        before=before,
        after={"value": setting.value},
        request_id=data.request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data={
        "key": setting.key, "value": setting.value, "description": setting.description
    })


def _promo_response(promo: PromoCode, usage_count: int = 0) -> PromoCodeResponse:
    return PromoCodeResponse(
        id=promo.id,
        code=promo.code,
        discount_percent=promo.discount_percent,
        plan_ids=promo.plan_ids,
        expires_at=promo.expires_at,
        active=promo.active,
        usage_count=usage_count,
        created_at=promo.created_at,
    )


@router.get("/promo-codes", response_model=ApiResponse[list[PromoCodeResponse]])
async def list_promo_codes(actor: AdminActor, db: AsyncSession = Depends(get_db)):
    promos = list(await db.scalars(select(PromoCode).order_by(PromoCode.created_at.desc())))
    counts = await PromoCodeService(db).usage_counts([promo.id for promo in promos])
    return ApiResponse(success=True, data=[_promo_response(promo, counts.get(promo.id, 0)) for promo in promos])


@router.post("/promo-codes", response_model=ApiResponse[PromoCodeResponse], status_code=201)
async def create_promo_code(
    data: PromoCodeCreate,
    actor: AdminActor,
    db: AsyncSession = Depends(get_db),
):
    existing_audit = await db.scalar(select(BillingAudit).where(BillingAudit.request_id == data.request_id))
    if existing_audit:
        promo = await db.get(PromoCode, int(existing_audit.entity_id))
        if not promo:
            raise HTTPException(404, "Промокод не найден")
        return ApiResponse(success=True, data=_promo_response(promo))

    code = data.code.strip().upper()
    if not code:
        raise HTTPException(422, "Укажите код промокода")
    if await db.scalar(select(PromoCode.id).where(PromoCode.code == code)):
        raise HTTPException(409, "Такой промокод уже существует")

    promo = PromoCode(
        code=code,
        discount_percent=data.discount_percent,
        plan_ids=data.plan_ids or None,
        expires_at=data.expires_at,
        active=data.active,
    )
    db.add(promo)
    await db.flush()
    db.add(BillingAudit(
        actor=actor,
        action="create",
        entity_type="promo_code",
        entity_id=str(promo.id),
        before={},
        after=_promo_response(promo).model_dump(mode="json"),
        request_id=data.request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data=_promo_response(promo))


@router.put("/promo-codes/{promo_id}", response_model=ApiResponse[PromoCodeResponse])
async def update_promo_code(
    promo_id: int,
    data: PromoCodeUpdate,
    actor: AdminActor,
    db: AsyncSession = Depends(get_db),
):
    promo_service = PromoCodeService(db)
    if await db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == data.request_id)):
        promo = await db.get(PromoCode, promo_id)
        if not promo:
            raise HTTPException(404, "Промокод не найден")
        counts = await promo_service.usage_counts([promo.id])
        return ApiResponse(success=True, data=_promo_response(promo, counts.get(promo.id, 0)))

    promo = await db.get(PromoCode, promo_id, with_for_update=True)
    if not promo:
        raise HTTPException(404, "Промокод не найден")
    before = _promo_response(promo).model_dump(mode="json")
    promo.discount_percent = data.discount_percent
    promo.plan_ids = data.plan_ids or None
    promo.expires_at = data.expires_at
    promo.active = data.active
    after = _promo_response(promo).model_dump(mode="json")
    db.add(BillingAudit(
        actor=actor,
        action="update",
        entity_type="promo_code",
        entity_id=str(promo.id),
        before=before,
        after=after,
        request_id=data.request_id,
    ))
    await db.commit()
    counts = await promo_service.usage_counts([promo.id])
    return ApiResponse(success=True, data=_promo_response(promo, counts.get(promo.id, 0)))


@router.delete("/promo-codes/{promo_id}", response_model=ApiResponse[dict])
async def delete_promo_code(
    promo_id: int,
    actor: AdminActor,
    request_id: str = Query(..., min_length=8, max_length=160),
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == request_id)):
        return ApiResponse(success=True, data={"ok": True})
    promo = await db.get(PromoCode, promo_id, with_for_update=True)
    if not promo:
        raise HTTPException(404, "Промокод не найден")
    counts = await PromoCodeService(db).usage_counts([promo.id])
    if counts.get(promo.id, 0) > 0:
        raise HTTPException(409, "Промокод уже использовался — деактивируйте его вместо удаления, чтобы сохранить статистику")
    before = _promo_response(promo).model_dump(mode="json")
    await db.delete(promo)
    db.add(BillingAudit(
        actor=actor,
        action="delete",
        entity_type="promo_code",
        entity_id=str(promo_id),
        before=before,
        after={},
        request_id=request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data={"ok": True})
