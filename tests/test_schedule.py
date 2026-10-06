"""Regression tests for schedules around local midnight (issue #9).

The RTC runs in UTC while schedules are configured in local time. In Europe/Berlin,
a window like 00:01-01:00 local lies on the previous UTC day, so any evaluation that
takes the calendar date from a UTC timestamp picks the wrong day.
"""

import datetime
import zoneinfo

import pytest

from wittypi4 import ScheduleConfiguration

UTC = datetime.UTC
BERLIN = zoneinfo.ZoneInfo("Europe/Berlin")

# configuration from issue #9, without the sun-relative fields being used
CONFIG = {
    "button_delay": "00:10",
    "force_on": False,
    "lat": 54.091349,
    "lon": 8.973584,
    "schedule": [{"name": f"EnergySaver{h // 2 + 1}a", "start": f"{h:02}:00", "stop": f"{h + 1:02}:00"} for h in range(2, 24, 2)]
    + [{"name": "EnergySaver1a", "start": "00:01", "stop": "01:00"}],
}


@pytest.fixture(params=[BERLIN, zoneinfo.ZoneInfo("America/New_York"), UTC], ids=str)
def tz(request):
    return request.param


@pytest.fixture
def sc(tz):
    return ScheduleConfiguration(CONFIG, tz=tz)


def local(tz, day, hour, minute, second=0):
    return datetime.datetime(2025, 12, day, hour, minute, second, tzinfo=tz)


@pytest.mark.parametrize("now_tz", [None, UTC], ids=["local-now", "utc-now"])
def test_active_after_local_midnight(sc, tz, now_tz):
    now = local(tz, 9, 0, 30)
    now = now.astimezone(now_tz) if now_tz else now

    assert sc.active(now)
    assert sc.next_shutdown(now) == local(tz, 9, 1, 0)
    assert sc.next_startup(now) == local(tz, 9, 2, 0)


@pytest.mark.parametrize("now_tz", [None, UTC], ids=["local-now", "utc-now"])
def test_startup_after_local_midnight(sc, tz, now_tz):
    # shortly after local midnight, before the 00:01 window opens
    now = local(tz, 9, 0, 0, 30)
    now = now.astimezone(now_tz) if now_tz else now

    assert not sc.active(now)
    assert sc.next_startup(now) == local(tz, 9, 0, 1)


def test_results_independent_of_now_timezone(sc, tz):
    """Every minute of a day must evaluate the same whether `now` is local or UTC."""
    start = local(tz, 8, 22, 0)
    for minute in range(0, 6 * 60):
        now = start + datetime.timedelta(minutes=minute)
        now_utc = now.astimezone(UTC)
        assert sc.active(now) == sc.active(now_utc), now
        assert sc.next_startup(now) == sc.next_startup(now_utc), now
        assert sc.next_shutdown(now) == sc.next_shutdown(now_utc), now


@pytest.mark.parametrize(
    ("now", "startup"),
    [
        (datetime.datetime(2025, 7, 1, 12, 0, tzinfo=UTC), datetime.datetime(2025, 7, 1, 22, 0, tzinfo=BERLIN)),
        (datetime.datetime(2025, 12, 1, 12, 0, tzinfo=UTC), datetime.datetime(2025, 12, 1, 22, 0, tzinfo=BERLIN)),
    ],
    ids=["summer", "winter"],
)
def test_default_timezone_follows_dst(monkeypatch, now, startup):
    """Without an explicit tz the system zone is used, including its DST rules."""
    monkeypatch.setenv("TZ", "Europe/Berlin")
    sc = ScheduleConfiguration({"schedule": [{"name": "evening", "start": "22:00", "stop": "23:00"}]})

    assert sc.next_startup(now) == startup
    assert sc.next_shutdown(startup) == startup + datetime.timedelta(hours=1)

