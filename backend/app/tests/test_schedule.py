import datetime
from zoneinfo import ZoneInfo

from schemas.workflow import IntervalScheduleSlot, WeeklyScheduleSlot
from services.schedule import (
    advance_due_slots,
    cron_to_weekly,
    earliest_next,
    next_slot_at,
    prepare_slots,
    weekly_to_cron,
)


TZ = "Europe/Moscow"


def test_weekly_cron_roundtrip() -> None:
    slot = cron_to_weekly("0 9 * * 1,2")
    assert slot is not None
    assert slot.time == "09:00"
    assert slot.weekdays == [1, 2]
    assert weekly_to_cron(slot.time, slot.weekdays) == "0 9 * * 1,2"


def test_two_weekly_slots_keep_independent_next() -> None:
    monday = WeeklyScheduleSlot(id="a", time="09:00", weekdays=[1, 2])
    wednesday = WeeklyScheduleSlot(id="b", time="11:30", weekdays=[3, 4, 5])
    now = datetime.datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo(TZ))  # Monday 08:00
    prepared = prepare_slots([monday, wednesday], TZ, enabled=True, now=now)
    first = earliest_next(prepared)
    assert first is not None
    local = first.astimezone(ZoneInfo(TZ))
    assert local.hour == 9 and local.minute == 0
    due = datetime.datetime(2026, 9, 14, 9, 0, tzinfo=ZoneInfo(TZ)).astimezone(datetime.UTC)
    advanced = advance_due_slots(prepared, TZ, due)
    times = sorted(slot.next_at.astimezone(ZoneInfo(TZ)).strftime("%a %H:%M") for slot in advanced if slot.next_at)
    assert any("11:30" in item for item in times)
    assert any("09:00" in item for item in times)


def test_interval_is_not_postponed_by_other_slot() -> None:
    weekly = WeeklyScheduleSlot(id="w", time="09:00", weekdays=[1])
    interval = IntervalScheduleSlot(id="i", every=2, unit="hours")
    now = datetime.datetime(2026, 9, 14, 8, 40, tzinfo=ZoneInfo(TZ))
    prepared = prepare_slots([weekly, interval], TZ, enabled=True, now=now)
    interval_next = next(slot.next_at for slot in prepared if slot.id == "i")
    weekly_fire = datetime.datetime(2026, 9, 14, 9, 0, tzinfo=ZoneInfo(TZ)).astimezone(datetime.UTC)
    advanced = advance_due_slots(prepared, TZ, weekly_fire)
    still_interval = next(slot.next_at for slot in advanced if slot.id == "i")
    assert still_interval == interval_next



def test_interval_minutes_aligns_to_clock() -> None:
    slot = IntervalScheduleSlot(every=30, unit="minutes")
    after = datetime.datetime(2026, 9, 14, 10, 17, tzinfo=ZoneInfo(TZ))
    nxt = next_slot_at(slot, TZ, after).astimezone(ZoneInfo(TZ))
    assert nxt.hour == 10 and nxt.minute == 30


def test_prepare_disabled_clears_next() -> None:
    slot = WeeklyScheduleSlot(time="09:00", weekdays=[1])
    prepared = prepare_slots([slot], TZ, enabled=False)
    assert prepared[0].next_at is None
    assert earliest_next(prepared) is None
