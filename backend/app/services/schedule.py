"""Несколько слотов автозапуска: дни недели + интервалы."""

from __future__ import annotations

import datetime
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from fastapi import HTTPException

from schemas.workflow import IntervalScheduleSlot, ScheduleSlot, WeeklyScheduleSlot, WorkflowSchedule

MAX_SCHEDULE_SLOTS = 20
INTERVAL_MAX = {"minutes": 1440, "hours": 168, "days": 365}


def weekly_to_cron(time: str, weekdays: list[int]) -> str:
    hour, minute = map(int, time.split(":"))
    days = "*" if len(set(weekdays)) >= 7 else ",".join(
        "0" if day == 7 else str(day) for day in sorted(set(weekdays))
    )
    return f"{minute} {hour} * * {days}"


def schedule_to_cron(schedule: WorkflowSchedule | None) -> str | None:
    if schedule is None:
        return None
    return weekly_to_cron(schedule.time, schedule.weekdays)


def cron_to_weekly(cron: str) -> WeeklyScheduleSlot | None:
    parts = cron.split()
    if len(parts) != 5:
        return None
    minute, hour, _dom, _month, dow = parts
    if not minute.isdigit() or not hour.isdigit():
        return None
    if dow == "*":
        weekdays = [1, 2, 3, 4, 5, 6, 7]
    else:
        weekdays = []
        for item in dow.split(","):
            if not item.isdigit():
                return None
            day = int(item)
            weekdays.append(7 if day == 0 else day)
        weekdays = [day for day in weekdays if 1 <= day <= 7]
        if not weekdays:
            return None
    return WeeklyScheduleSlot(
        time=f"{int(hour):02d}:{int(minute):02d}",
        weekdays=sorted(set(weekdays)),
    )


def _tz(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, f"Некорректный часовой пояс: {timezone}") from exc


def _aware(value: datetime.datetime, timezone: str) -> datetime.datetime:
    tz = _tz(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def next_weekly_at(
    slot: WeeklyScheduleSlot,
    timezone: str,
    after: datetime.datetime | None = None,
) -> datetime.datetime:
    tz = _tz(timezone)
    start = _aware(after or datetime.datetime.now(tz), timezone)
    try:
        nxt = croniter(weekly_to_cron(slot.time, slot.weekdays), start).get_next(datetime.datetime)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"Некорректное расписание: {exc}") from exc
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=tz)
    return nxt.astimezone(datetime.UTC)


def _interval_delta(slot: IntervalScheduleSlot) -> datetime.timedelta:
    if slot.unit == "minutes":
        return datetime.timedelta(minutes=slot.every)
    if slot.unit == "hours":
        return datetime.timedelta(hours=slot.every)
    return datetime.timedelta(days=slot.every)


def next_interval_at(
    slot: IntervalScheduleSlot,
    timezone: str,
    after: datetime.datetime | None = None,
) -> datetime.datetime:
    tz = _tz(timezone)
    start = _aware(after or datetime.datetime.now(tz), timezone)
    if slot.unit == "minutes":
        midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed = (start - midnight).total_seconds() / 60
        steps = int(elapsed // slot.every) + 1
        return (midnight + datetime.timedelta(minutes=steps * slot.every)).astimezone(datetime.UTC)
    if slot.unit == "hours":
        if slot.every <= 12 and 24 % slot.every == 0:
            cursor = start.replace(minute=0, second=0, microsecond=0)
            if cursor <= start:
                cursor += datetime.timedelta(hours=1)
            while cursor.hour % slot.every != 0:
                cursor += datetime.timedelta(hours=1)
            return cursor.astimezone(datetime.UTC)
        return (start.replace(second=0, microsecond=0) + datetime.timedelta(hours=slot.every)).astimezone(datetime.UTC)
    return (start.replace(second=0, microsecond=0) + _interval_delta(slot)).astimezone(datetime.UTC)


def next_slot_at(
    slot: ScheduleSlot,
    timezone: str,
    after: datetime.datetime | None = None,
) -> datetime.datetime:
    if isinstance(slot, WeeklyScheduleSlot):
        return next_weekly_at(slot, timezone, after)
    return next_interval_at(slot, timezone, after)


def _slot_key(slot: ScheduleSlot) -> tuple:
    if isinstance(slot, WeeklyScheduleSlot):
        return ("weekly", slot.time, tuple(slot.weekdays))
    return ("interval", slot.every, slot.unit)


def slots_from_legacy(cron: str | None) -> list[ScheduleSlot]:
    if not cron:
        return []
    weekly = cron_to_weekly(cron)
    return [weekly] if weekly else []


def normalize_slots(slots: list[ScheduleSlot]) -> list[ScheduleSlot]:
    if len(slots) > MAX_SCHEDULE_SLOTS:
        raise HTTPException(422, f"Не больше {MAX_SCHEDULE_SLOTS} слотов расписания")
    seen: set[tuple] = set()
    unique: list[ScheduleSlot] = []
    for slot in slots:
        if isinstance(slot, IntervalScheduleSlot):
            limit = INTERVAL_MAX[slot.unit]
            if slot.every > limit:
                raise HTTPException(422, f"Интервал: максимум {limit} {slot.unit}")
        key = _slot_key(slot)
        if key in seen:
            continue
        seen.add(key)
        if not slot.id:
            slot.id = uuid.uuid4().hex[:12]
        unique.append(slot)
    return unique


def dump_slots(slots: list[ScheduleSlot]) -> list[dict]:
    payload = []
    for slot in slots:
        item = slot.model_dump(mode="json")
        if slot.next_at is not None:
            item["next_at"] = slot.next_at.astimezone(datetime.UTC).isoformat()
        payload.append(item)
    return payload


def load_slots(raw: object) -> list[ScheduleSlot]:
    if not raw:
        return []
    items = raw if isinstance(raw, list) else []
    slots: list[ScheduleSlot] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") or ("interval" if "every" in item else "weekly")
        try:
            if kind == "interval":
                slots.append(IntervalScheduleSlot.model_validate(item))
            else:
                slots.append(WeeklyScheduleSlot.model_validate(item))
        except ValueError:
            continue
    return slots


def prepare_slots(
    slots: list[ScheduleSlot],
    timezone: str,
    *,
    enabled: bool,
    previous: list[ScheduleSlot] | None = None,
    now: datetime.datetime | None = None,
) -> list[ScheduleSlot]:
    slots = normalize_slots(slots)
    if not enabled:
        for slot in slots:
            slot.next_at = None
        return slots
    previous_by_id = {slot.id: slot for slot in previous or [] if slot.id}
    previous_by_key = {_slot_key(slot): slot for slot in previous or []}
    moment = now or datetime.datetime.now(datetime.UTC)
    prepared: list[ScheduleSlot] = []
    for slot in slots:
        prior = previous_by_id.get(slot.id) or previous_by_key.get(_slot_key(slot))
        if prior and _slot_key(prior) == _slot_key(slot) and prior.next_at and prior.next_at > moment:
            slot.next_at = prior.next_at
        else:
            slot.next_at = next_slot_at(slot, timezone, moment)
        prepared.append(slot)
    return prepared


def earliest_next(slots: list[ScheduleSlot]) -> datetime.datetime | None:
    times = [slot.next_at for slot in slots if slot.next_at is not None]
    return min(times) if times else None


def derived_cron(slots: list[ScheduleSlot], enabled: bool) -> str | None:
    if not enabled or not slots:
        return None
    weekly = next((slot for slot in slots if isinstance(slot, WeeklyScheduleSlot)), None)
    if weekly:
        return weekly_to_cron(weekly.time, weekly.weekdays)
    interval = next((slot for slot in slots if isinstance(slot, IntervalScheduleSlot)), None)
    if interval and interval.unit == "minutes" and interval.every <= 59:
        return f"*/{interval.every} * * * *"
    if interval and interval.unit == "hours" and interval.every <= 23:
        return f"0 */{interval.every} * * *"
    if interval and interval.unit == "days" and interval.every <= 31:
        return f"0 9 */{interval.every} * *"
    return "0 9 * * *"


def advance_due_slots(
    slots: list[ScheduleSlot],
    timezone: str,
    now: datetime.datetime,
) -> list[ScheduleSlot]:
    advanced: list[ScheduleSlot] = []
    for slot in slots:
        if slot.next_at is None or slot.next_at > now:
            advanced.append(slot)
            continue
        cursor = slot.next_at
        guard = 0
        while cursor <= now and guard < 10_000:
            cursor = next_slot_at(slot, timezone, cursor)
            guard += 1
        slot.next_at = cursor
        advanced.append(slot)
    return advanced
