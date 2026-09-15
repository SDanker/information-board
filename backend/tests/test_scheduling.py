from datetime import date, datetime, time

from app.scheduling import is_item_scheduled_now


def test_no_restrictions_always_scheduled():
    assert is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=None, start_time=None, end_time=None
    )


def test_inactive_never_scheduled():
    assert not is_item_scheduled_now(
        is_active=False, start_date=None, end_date=None, days_of_week=None, start_time=None, end_time=None
    )


def test_date_range_excludes_outside_window():
    moment = datetime(2026, 1, 15, 12, 0)
    assert not is_item_scheduled_now(
        is_active=True, start_date=date(2026, 2, 1), end_date=None, days_of_week=None, start_time=None, end_time=None, at=moment
    )
    assert not is_item_scheduled_now(
        is_active=True, start_date=None, end_date=date(2026, 1, 1), days_of_week=None, start_time=None, end_time=None, at=moment
    )
    assert is_item_scheduled_now(
        is_active=True, start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), days_of_week=None, start_time=None, end_time=None, at=moment
    )


def test_days_of_week_thursday_is_3():
    thursday = datetime(2026, 1, 15, 12, 0)  # 15 January 2026 is a Thursday
    assert thursday.weekday() == 3
    assert is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=[3], start_time=None, end_time=None, at=thursday
    )
    assert not is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=[0, 1, 2], start_time=None, end_time=None, at=thursday
    )


def test_time_range_normal():
    at = datetime(2026, 1, 15, 10, 0)
    assert is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=None, start_time=time(9, 0), end_time=time(18, 0), at=at
    )
    assert not is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=None, start_time=time(11, 0), end_time=time(18, 0), at=at
    )


def test_time_range_overnight_wraps_midnight():
    late_night = datetime(2026, 1, 15, 23, 30)
    early_morning = datetime(2026, 1, 15, 3, 0)
    midday = datetime(2026, 1, 15, 12, 0)
    for at in (late_night, early_morning):
        assert is_item_scheduled_now(
            is_active=True, start_date=None, end_date=None, days_of_week=None, start_time=time(22, 0), end_time=time(6, 0), at=at
        )
    assert not is_item_scheduled_now(
        is_active=True, start_date=None, end_date=None, days_of_week=None, start_time=time(22, 0), end_time=time(6, 0), at=midday
    )
