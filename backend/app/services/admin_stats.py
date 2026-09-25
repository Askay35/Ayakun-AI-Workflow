import datetime
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Row, and_, distinct, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.functions import FunctionElement

from helper import utcnow
from models.billing import Payment, Plan, Subscription, UsageRecord
from models.user import AuthIdentity, User
from models.workflow import RunStatus, Workflow, WorkflowRun, WorkflowStatus
from schemas.admin import (
    AdminStatsCount,
    AdminStatsMetric,
    AdminStatsPlan,
    AdminStatsPoint,
    AdminStatsReferrer,
    AdminStatsResponse,
    AdminStatsTotals,
)
from schemas.billing import PaymentStatus

Granularity = Literal["day", "week", "month"]
NO_PLAN = "none"
# Покупки, выданные из админки, не приносят денег и в доход не входят.
MANUAL_PAYMENT_PROVIDER = "admin"
TOP_REFERRERS = 10


def _pct(value: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((value - previous) / previous * 100, 1)


def _metric(value: Decimal | float | int | None, previous: Decimal | float | int | None) -> AdminStatsMetric:
    current, before = float(value or 0), float(previous or 0)
    return AdminStatsMetric(value=current, previous=before, delta=current - before, delta_pct=_pct(current, before))


def _bucket_start(now_local: datetime.datetime, granularity: Granularity) -> datetime.datetime:
    day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        return day - datetime.timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def _shift(start: datetime.datetime, granularity: Granularity, steps: int) -> datetime.datetime:
    if granularity == "day":
        return start + datetime.timedelta(days=steps)
    if granularity == "week":
        return start + datetime.timedelta(weeks=steps)
    months = start.year * 12 + start.month - 1 + steps
    return start.replace(year=months // 12, month=months % 12 + 1)


@dataclass(frozen=True)
class _Period:
    granularity: Granularity
    timezone: str
    starts: list[datetime.datetime]
    series_from: datetime.datetime
    period_start: datetime.datetime
    previous_start: datetime.datetime


class AdminStatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def stats(self, granularity: Granularity, points: int, timezone: str) -> AdminStatsResponse:
        try:
            tz = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(422, "Неизвестный часовой пояс") from exc

        now = utcnow()
        current = _bucket_start(now.astimezone(tz).replace(tzinfo=None), granularity)
        # Лишний первый интервал нужен только для прироста первой точки графика.
        starts = [_shift(current, granularity, -offset) for offset in range(points, -1, -1)]

        def to_utc(local: datetime.datetime) -> datetime.datetime:
            return local.replace(tzinfo=tz).astimezone(datetime.UTC)

        period_start = to_utc(starts[1])
        period = _Period(
            granularity=granularity,
            timezone=timezone,
            starts=starts,
            series_from=to_utc(starts[0]),
            period_start=period_start,
            previous_start=period_start - (now - period_start),
        )
        paid = and_(Payment.status == PaymentStatus.succeeded, Payment.provider != MANUAL_PAYMENT_PROVIDER)

        registrations = await self._window(period, User.created_at, lambda: func.count(User.id))
        referral_registrations = await self._window(
            period, User.created_at, lambda: func.count(User.id), User.referred_by_id.is_not(None)
        )
        revenue = await self._window(period, Payment.created_at, lambda: func.sum(Payment.amount), paid)
        payments = await self._window(period, Payment.created_at, lambda: func.count(Payment.id), paid)
        paying_users = await self._window(
            period, Payment.created_at, lambda: func.count(distinct(Payment.user_id)), paid
        )
        active_users = await self._window(
            period, WorkflowRun.created_at, lambda: func.count(distinct(WorkflowRun.owner_id))
        )
        runs = await self._window(period, WorkflowRun.created_at, lambda: func.count(WorkflowRun.id))
        avg_check = _metric(
            revenue.value / payments.value if payments.value else 0,
            revenue.previous / payments.previous if payments.previous else 0,
        )

        converted = await self.db.scalar(
            select(func.count(distinct(User.id)))
            .join(Payment, Payment.user_id == User.id)
            .where(User.created_at >= period_start, paid)
        ) or 0
        conversion_pct = round(converted / registrations.value * 100, 1) if registrations.value else None
        credits_spent = await self.db.scalar(
            select(func.coalesce(func.sum(WorkflowRun.cost), 0)).where(WorkflowRun.created_at >= period_start)
        )
        provider_cost = await self.db.scalar(
            select(func.coalesce(func.sum(UsageRecord.provider_cost_usd), 0))
            .where(UsageRecord.created_at >= period_start)
        )

        active_subscription = and_(Subscription.status == "active", Subscription.expires_at > now)
        totals_row = (await self.db.execute(select(
            select(func.count(User.id)).scalar_subquery(),
            select(func.count(distinct(Payment.user_id))).where(paid).scalar_subquery(),
            select(func.coalesce(func.sum(Payment.amount), 0)).where(paid).scalar_subquery(),
            select(func.count(Subscription.id)).where(active_subscription).scalar_subquery(),
            select(func.count(Workflow.id)).scalar_subquery(),
            select(func.count(Workflow.id)).where(Workflow.status == WorkflowStatus.published).scalar_subquery(),
            select(func.count(WorkflowRun.id)).scalar_subquery(),
        ))).one()
        totals = AdminStatsTotals(
            users=totals_row[0],
            paying_users=totals_row[1],
            revenue=float(totals_row[2]),
            active_subscriptions=totals_row[3],
            workflows=totals_row[4],
            published_workflows=totals_row[5],
            runs=totals_row[6],
        )

        series = await self._series(period, paid)
        plans = await self._plans(period_start, paid, active_subscription)
        top_referrers = await self._top_referrers(period_start, paid)

        signup_rows = await self.db.execute(
            select(AuthIdentity.provider, func.count(distinct(AuthIdentity.user_id)))
            .join(User, User.id == AuthIdentity.user_id)
            .where(User.created_at >= period_start)
            .group_by(AuthIdentity.provider)
        )
        status_rows = await self.db.execute(
            select(WorkflowRun.status, func.count(WorkflowRun.id))
            .where(WorkflowRun.created_at >= period_start)
            .group_by(WorkflowRun.status)
        )

        return AdminStatsResponse(
            granularity=granularity,
            timezone=timezone,
            period_start=period.period_start,
            previous_start=period.previous_start,
            registrations=registrations,
            referral_registrations=referral_registrations,
            revenue=revenue,
            payments=payments,
            avg_check=avg_check,
            paying_users=paying_users,
            active_users=active_users,
            runs=runs,
            conversion_pct=conversion_pct,
            credits_spent=float(credits_spent or 0),
            provider_cost_usd=float(provider_cost or 0),
            totals=totals,
            series=series,
            plans=plans,
            top_referrers=top_referrers,
            signup_providers=sorted(
                (AdminStatsCount(key=provider.value, count=count) for provider, count in signup_rows.all()),
                key=lambda item: -item.count,
            ),
            run_statuses=sorted(
                (AdminStatsCount(key=status.value, count=count) for status, count in status_rows.all()),
                key=lambda item: -item.count,
            ),
        )

    async def _window(
        self,
        period: _Period,
        column: InstrumentedAttribute[datetime.datetime],
        aggregate: Callable[[], FunctionElement],
        where: ColumnElement[bool] | None = None,
    ) -> AdminStatsMetric:
        """Значение за выбранный период и за такой же по длине период перед ним."""
        query = select(
            aggregate().filter(column >= period.period_start),
            aggregate().filter(column < period.period_start),
        ).where(column >= period.previous_start)
        if where is not None:
            query = query.where(where)
        value, previous = (await self.db.execute(query)).one()
        return _metric(value, previous)

    async def _by_bucket(
        self,
        period: _Period,
        column: InstrumentedAttribute[datetime.datetime],
        *values: ColumnElement,
        where: ColumnElement[bool] | None = None,
        extra: InstrumentedAttribute | None = None,
    ) -> list[Row]:
        bucket = func.date_trunc(period.granularity, func.timezone(period.timezone, column)).label("bucket")
        columns: list[ColumnElement] = [bucket]
        group = [literal_column("bucket")]
        if extra is not None:
            columns.append(extra.label("extra"))
            group.append(literal_column("extra"))
        query = select(*columns, *values).where(column >= period.series_from)
        if where is not None:
            query = query.where(where)
        return list((await self.db.execute(query.group_by(*group))).all())

    async def _series(self, period: _Period, paid: ColumnElement[bool]) -> list[AdminStatsPoint]:
        registrations = {
            bucket: (total, referral)
            for bucket, total, referral in await self._by_bucket(
                period,
                User.created_at,
                func.count(User.id),
                func.count(User.id).filter(User.referred_by_id.is_not(None)),
            )
        }
        plan_codes: dict[int, str] = dict((await self.db.execute(select(Plan.id, Plan.code))).all())
        revenue: dict[datetime.datetime, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        payments: dict[datetime.datetime, int] = defaultdict(int)
        for bucket, plan_id, amount, count in await self._by_bucket(
            period,
            Payment.created_at,
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
            where=paid,
            extra=Payment.plan_id,
        ):
            revenue[bucket][plan_codes.get(plan_id, NO_PLAN)] += float(amount)
            payments[bucket] += count
        runs = {
            bucket: (total, failed, cost)
            for bucket, total, failed, cost in await self._by_bucket(
                period,
                WorkflowRun.created_at,
                func.count(WorkflowRun.id),
                func.count(WorkflowRun.id).filter(WorkflowRun.status == RunStatus.failed),
                func.coalesce(func.sum(WorkflowRun.cost), 0),
            )
        }
        users_total = await self.db.scalar(
            select(func.count(User.id)).where(User.created_at < period.series_from)
        ) or 0

        points: list[AdminStatsPoint] = []
        previous: int | None = None
        for start in period.starts:
            count, referral = registrations.get(start, (0, 0))
            users_total += count
            if previous is not None:
                by_plan = dict(revenue.get(start, {}))
                total_runs, failed_runs, cost = runs.get(start, (0, 0, 0))
                points.append(AdminStatsPoint(
                    start=start.date(),
                    registrations=count,
                    registrations_delta=count - previous,
                    registrations_delta_pct=_pct(count, previous),
                    referral_registrations=referral,
                    users_total=users_total,
                    revenue=sum(by_plan.values()),
                    revenue_by_plan=by_plan,
                    payments=payments.get(start, 0),
                    runs=total_runs,
                    failed_runs=failed_runs,
                    credits_spent=float(cost),
                ))
            previous = count
        return points

    async def _plans(
        self,
        period_start: datetime.datetime,
        paid: ColumnElement[bool],
        active_subscription: ColumnElement[bool],
    ) -> list[AdminStatsPlan]:
        in_period = Payment.created_at >= period_start
        revenue_rows = {
            plan_id: row
            for plan_id, *row in (await self.db.execute(
                select(
                    Payment.plan_id,
                    func.coalesce(func.sum(Payment.amount).filter(in_period), 0),
                    func.count(Payment.id).filter(in_period),
                    func.coalesce(func.sum(Payment.amount), 0),
                    func.count(Payment.id),
                )
                .where(paid)
                .group_by(Payment.plan_id)
            )).all()
        }
        subscriptions = dict((await self.db.execute(
            select(Subscription.plan_id, func.count(Subscription.id))
            .where(active_subscription)
            .group_by(Subscription.plan_id)
        )).all())

        result: list[AdminStatsPlan] = []
        for plan in await self.db.scalars(select(Plan).order_by(Plan.price)):
            period_revenue, period_count, total_revenue, total_count = revenue_rows.get(plan.id, (0, 0, 0, 0))
            active = subscriptions.get(plan.id, 0)
            if plan.price <= 0 and not total_count and not active:
                continue
            result.append(AdminStatsPlan(
                code=plan.code,
                name=plan.name,
                revenue=float(period_revenue),
                payments=period_count,
                revenue_total=float(total_revenue),
                payments_total=total_count,
                active_subscriptions=active,
            ))
        if None in revenue_rows:
            period_revenue, period_count, total_revenue, total_count = revenue_rows[None]
            result.append(AdminStatsPlan(
                code=NO_PLAN,
                name="Без тарифа",
                revenue=float(period_revenue),
                payments=period_count,
                revenue_total=float(total_revenue),
                payments_total=total_count,
                active_subscriptions=0,
            ))
        return result

    async def _top_referrers(
        self,
        period_start: datetime.datetime,
        paid: ColumnElement[bool],
    ) -> list[AdminStatsReferrer]:
        period_count = func.count(User.id).filter(User.created_at >= period_start).label("period_count")
        total_count = func.count(User.id).label("total_count")
        rows = (await self.db.execute(
            select(User.referred_by_id, period_count, total_count)
            .where(User.referred_by_id.is_not(None))
            .group_by(User.referred_by_id)
            .order_by(period_count.desc(), total_count.desc())
            .limit(TOP_REFERRERS)
        )).all()
        if not rows:
            return []
        ids = [row[0] for row in rows]
        referrers = {
            user_id: (name, email)
            for user_id, name, email in (await self.db.execute(
                select(User.id, User.name, User.email).where(User.id.in_(ids))
            )).all()
        }
        conversions = {
            referrer_id: (count, amount)
            for referrer_id, count, amount in (await self.db.execute(
                select(User.referred_by_id, func.count(distinct(Payment.user_id)), func.sum(Payment.amount))
                .join(Payment, Payment.user_id == User.id)
                .where(User.referred_by_id.in_(ids), paid)
                .group_by(User.referred_by_id)
            )).all()
        }
        result: list[AdminStatsReferrer] = []
        for referrer_id, period, total in rows:
            name, email = referrers.get(referrer_id, (f"ID {referrer_id}", None))
            paid_count, amount = conversions.get(referrer_id, (0, 0))
            result.append(AdminStatsReferrer(
                user_id=referrer_id,
                name=name,
                email=email,
                referrals_period=period,
                referrals_total=total,
                paid_referrals=paid_count,
                revenue=float(amount or 0),
            ))
        return result
