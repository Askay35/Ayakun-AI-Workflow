from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps.admin import AdminActor
from deps.database import get_db
from models.billing import BillingAudit, Plan, PricingRate, RuntimeSetting
from schemas.billing import (
    AdminPlanUpdate,
    PlanResponse,
    PricingRateResponse,
    PricingRateUpdate,
    RuntimeSettingUpdate,
)
from schemas.common import ApiResponse

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
    plan.limits = {
        **{key: value for key, value in plan.limits.items() if key != "parallel_runs"},
        "included_credits": float(data.included_credits),
        "run_cap_credits": float(data.run_cap_credits),
    }
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
    setting.value = data.value
    db.add(BillingAudit(
        actor=actor,
        action="update",
        entity_type="runtime_setting",
        entity_id=key,
        before=before,
        after={"value": data.value},
        request_id=data.request_id,
    ))
    await db.commit()
    return ApiResponse(success=True, data={
        "key": setting.key, "value": setting.value, "description": setting.description
    })
