"""Regression tests for schedules around local midnight (issue #9).

The RTC runs in UTC while schedules are configured in local time. In Europe/Berlin,
a window like 00:01-01:00 local lies on the previous UTC day, so any evaluation that
takes the calendar date from a UTC timestamp picks the wrong day.
"""

import datetime
import zoneinfo

import pytest

from wittypi4 import ButtonEntry, ScheduleConfiguration

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



# Configuration edge cases


@pytest.mark.parametrize("config", [{}, {"schedule": []}, {"schedule": None}], ids=["missing", "empty", "null"])
def test_no_schedule_forces_on(config):
    sc = ScheduleConfiguration(config, tz=BERLIN)
    now = local(BERLIN, 9, 12, 0)

    assert sc.force_on
    assert sc.active(now)
    assert sc.next_shutdown(now) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("00:10", datetime.timedelta(minutes=10)), ("01:30", datetime.timedelta(minutes=90)), ("soon", None), (None, None)],
)
def test_button_delay(value, expected):
    sc = ScheduleConfiguration({"button_delay": value, "schedule": CONFIG["schedule"]}, tz=BERLIN)
    assert sc.button_delay == expected


def test_sun_relative_without_location(monkeypatch):
    monkeypatch.setattr("wittypi4._parse_geolocation_file", lambda: None)
    config = {"schedule": [{"name": "dawn", "start": "sunrise-01:00", "stop": "sunrise+01:00"},
                           {"name": "noon", "start": "12:00", "stop": "13:00"}]}

    sc = ScheduleConfiguration(config, tz=BERLIN)

    assert [e.name for e in sc.entries] == ["noon"]
    assert sc.next_startup(local(BERLIN, 9, 6, 0)) == local(BERLIN, 9, 12, 0)


def test_location_from_geolocation_file(monkeypatch):
    monkeypatch.setattr("wittypi4._parse_geolocation_file", lambda: (54.09, 8.97))
    sc = ScheduleConfiguration({"schedule": [{"name": "dawn", "start": "sunrise+00:00", "stop": "sunrise+01:00"}]}, tz=BERLIN)

    sunrise = sc.next_startup(local(BERLIN, 9, 0, 0))
    assert local(BERLIN, 9, 7, 0) < sunrise < local(BERLIN, 9, 10, 0)


def test_always_on_has_no_shutdown():
    sc = ScheduleConfiguration({"schedule": [{"name": "always", "start": "00:00", "stop": "24:00"}]}, tz=BERLIN)
    assert sc.next_shutdown(local(BERLIN, 9, 12, 0)) is None


def test_adjacent_entries_merge():
    config = {"schedule": [{"name": "a", "start": "10:00", "stop": "11:00"},
                           {"name": "b", "start": "11:00", "stop": "12:00"}]}
    sc = ScheduleConfiguration(config, tz=BERLIN)

    assert sc.next_shutdown(local(BERLIN, 9, 10, 30)) == local(BERLIN, 9, 12, 0)


def test_overlapping_entries_merge():
    config = {"schedule": [{"name": "a", "start": "10:00", "stop": "11:30"},
                           {"name": "b", "start": "11:00", "stop": "12:00"}]}
    sc = ScheduleConfiguration(config, tz=BERLIN)

    assert sc.next_shutdown(local(BERLIN, 9, 10, 30)) == local(BERLIN, 9, 12, 0)


# Manual power-on


@pytest.mark.parametrize(
    ("uptime_s", "delay", "active"),
    [(60, datetime.timedelta(minutes=10), True), (3600, datetime.timedelta(minutes=10), False), (60, None, False)],
    ids=["within-delay", "after-delay", "no-delay"],
)
def test_button_entry(monkeypatch, uptime_s, delay, active):
    monkeypatch.setattr("wittypi4.time.monotonic", lambda: uptime_s)
    entry = ButtonEntry(delay, tz=BERLIN)

    assert entry.active() is active
    assert entry.next_start() is None


def test_button_entry_keeps_system_on(monkeypatch):
    monkeypatch.setattr("wittypi4.time.monotonic", lambda: 60)
    sc = ScheduleConfiguration({"schedule": [{"name": "noon", "start": "12:00", "stop": "13:00"}]}, tz=BERLIN)
    now = datetime.datetime.now(BERLIN)
    sc.entries.append(ButtonEntry(datetime.timedelta(minutes=10), tz=BERLIN))

    assert sc.active(now)
    shutdown = sc.next_shutdown(now)
    assert shutdown is not None and now < shutdown <= now + datetime.timedelta(hours=24)
