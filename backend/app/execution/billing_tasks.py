"""Celery-задачи тарифов: окончание периода и напоминание о продлении."""

from __future__ import annotations

import asyncio
import datetime
import logging

import httpx

from core.config import settings
from execution.celery_app import celery_app
from execution.tasks import task_session_factory
from helper import escape_telegram_markdown
from models.billing import Plan
from models.user import User
from services.billing.subscriptions import SubscriptionService
from services.providers import SMTPEmailProvider, TelegramNotificationProvider

logger = logging.getLogger(__name__)

REMIND_BEFORE = datetime.timedelta(days=3)


async def _expire_subscriptions() -> int:
    task_engine, TaskSession = task_session_factory()
    try:
        async with TaskSession() as db:
            expired = await SubscriptionService(db).expire_due()
        for user_id in expired:
            logger.info("Период тарифа закончился", extra={"event": "subscription.expired", "owner_id": user_id})
        return len(expired)
    finally:
        await task_engine.dispose()


@celery_app.task(name="execution.billing_tasks.expire_subscriptions")
def expire_subscriptions() -> int:
    return asyncio.run(_expire_subscriptions())


def _reminder_text(plan_name: str, expires_at: datetime.datetime) -> str:
    date = expires_at.astimezone(datetime.UTC).strftime("%d.%m.%Y")
    return (
        f"Тариф «{plan_name}» в Ayakun действует до {date}. "
        "Неиспользованные токены сгорят в конце периода — продлите тариф или перейдите на старший, "
        f"чтобы токены сохранились: {settings.frontend_url.rstrip('/')}/billing"
    )


async def _remind_expiring() -> int:
    task_engine, TaskSession = task_session_factory()
    sent = 0
    try:
        async with TaskSession() as db, httpx.AsyncClient() as client:
            telegram = TelegramNotificationProvider(client)
            email = SMTPEmailProvider()
            for subscription in await SubscriptionService(db).due_for_reminder(REMIND_BEFORE):
                user = await db.get(User, subscription.user_id)
                plan = subscription.plan or await db.get(Plan, subscription.plan_id)
                if user is None or plan is None:
                    continue
                text = _reminder_text(plan.name, subscription.expires_at)
                delivered = False
                try:
                    if user.chat_id:
                        await telegram.send(str(user.chat_id), escape_telegram_markdown(text))
                        delivered = True
                    elif user.email:
                        await email.send(user.email, "Тариф Ayakun скоро закончится", text)
                        delivered = True
                except Exception:
                    logger.warning(
                        "Не удалось отправить напоминание о тарифе",
                        extra={"event": "subscription.remind_failed", "owner_id": user.id},
                    )
                # Отмечаем и при неудаче: напоминание — не критичная операция, без повторов каждый час.
                subscription.reminded_at = datetime.datetime.now(datetime.UTC)
                await db.commit()
                sent += int(delivered)
        return sent
    finally:
        await task_engine.dispose()


@celery_app.task(name="execution.billing_tasks.remind_expiring_subscriptions")
def remind_expiring_subscriptions() -> int:
    return asyncio.run(_remind_expiring())
