import asyncio
import os
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from models.billing import BillingReservation, UsageRecord, Wallet
from models.user import User
from models.workflow import Workflow, WorkflowRun, WorkflowVersion
from services.billing import BillingService

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="requires disposable PostgreSQL data",
)


@pytest.mark.asyncio
async def test_concurrent_reserves_cannot_exceed_balance() -> None:
    engine = create_async_engine(settings.db_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = f"billing-test-{uuid.uuid4()}@example.invalid"
    user_id: int | None = None
    try:
        async with sessions() as db:
            user = User(name="Billing test", email=email)
            db.add(user)
            await db.flush()
            user_id = user.id
            workflow = Workflow(owner_id=user.id, name="Test", draft_graph={"nodes": []})
            db.add(workflow)
            await db.flush()
            version = WorkflowVersion(workflow_id=workflow.id, version=1, graph_snapshot={"nodes": []})
            db.add(version)
            await db.flush()
            workflow.published_version_id = version.id
            runs = [
                WorkflowRun(
                    workflow_id=workflow.id,
                    workflow_version_id=version.id,
                    owner_id=user.id,
                )
                for _ in range(6)
            ]
            db.add_all(runs)
            await db.commit()
            run_ids = [run.id for run in runs]
            await BillingService(db).ensure_initial_credit(user)

        async def reserve(run_id: uuid.UUID) -> bool:
            async with sessions() as db:
                user = await db.get(User, user_id)
                try:
                    await BillingService(db).reserve_run(user, run_id, f"test:{run_id}")
                    return True
                except HTTPException as exc:
                    await db.rollback()
                    assert exc.status_code == 402
                    return False

        results = await asyncio.gather(*(reserve(run_id) for run_id in run_ids))
        assert sum(results) == 1

        async with sessions() as db:
            wallet = await db.get(Wallet, user_id)
            reserved = await db.scalar(
                select(func.coalesce(func.sum(BillingReservation.amount), 0))
                .where(BillingReservation.user_id == user_id)
            )
            assert wallet.balance == Decimal("100")
            assert wallet.reserved == Decimal("100")
            assert Decimal(reserved) == Decimal("100")
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_charge_and_release_are_idempotent_and_never_go_negative() -> None:
    engine = create_async_engine(settings.db_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = f"billing-settle-{uuid.uuid4()}@example.invalid"
    user_id: int | None = None
    try:
        async with sessions() as db:
            user = User(name="Billing settle", email=email)
            db.add(user)
            await db.flush()
            user_id = user.id
            workflow = Workflow(owner_id=user.id, name="Test", draft_graph={"nodes": []})
            db.add(workflow)
            await db.flush()
            version = WorkflowVersion(workflow_id=workflow.id, version=1, graph_snapshot={"nodes": []})
            db.add(version)
            await db.flush()
            run = WorkflowRun(
                workflow_id=workflow.id,
                workflow_version_id=version.id,
                owner_id=user.id,
            )
            db.add(run)
            await db.commit()

            billing = BillingService(db)
            await billing.ensure_initial_credit(user)
            await billing.reserve_run(user, run.id, f"run:{run.id}")
            details = {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "input_cache_miss_tokens": 100,
                "output_tokens": 50,
                "provider_cost_usd": "0.01",
            }
            for _ in range(2):
                await billing.charge_reservation(
                    user,
                    f"run:{run.id}",
                    Decimal("10"),
                    f"charge:{run.id}:node",
                    workflow_run_id=run.id,
                    units=150,
                    details=details,
                )
            for _ in range(2):
                await billing.release_run(user, f"run:{run.id}", f"release:{run.id}")

            await db.refresh(run)
            wallet = await db.get(Wallet, user.id)
            usage_count = await db.scalar(
                select(func.count(UsageRecord.id)).where(UsageRecord.workflow_run_id == run.id)
            )
            assert wallet.balance == Decimal("90")
            assert wallet.reserved == Decimal("0")
            assert run.cost == Decimal("10")
            assert usage_count == 1
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()
