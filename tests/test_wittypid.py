"""Tests for the wittypid daemon against an in-memory WittyPi."""

import datetime
import io
import os
import pathlib

import pytest
import yaml

import wittypi4
from conftest import UTC, fake_firmware_tick
from wittypi4 import ActionReason, ScheduleConfiguration, wittypid

# schedule from issue #9, as the daemon reads it
SCHEDULE_YML = """
button_delay: 00:10
force_on: false
lat: 54.091349
lon: 8.973584
schedule:
- {name: EnergySaver1a, start: 00:01, stop: 01:00}
- {name: EnergySaver2a, start: 02:00, stop: 03:00}
- {name: EnergySaver3a, start: 04:00, stop: 05:00}
- {name: EnergySaver4a, start: 06:00, stop: 07:00}
- {name: EnergySaver5a, start: 08:00, stop: 09:00}
- {name: EnergySaver6a, start: '10:00', stop: '11:00'}
- {name: EnergySaver7a, start: '12:00', stop: '13:00'}
- {name: EnergySaver8a, start: '14:00', stop: '15:00'}
- {name: EnergySaver9a, start: '16:00', stop: '17:00'}
- {name: EnergySaver10a, start: '18:00', stop: '19:00'}
- {name: EnergySaver11a, start: '20:00', stop: '21:00'}
- {name: EnergySaver12a, start: '22:00', stop: '23:00'}
"""


@pytest.fixture
def daemon(bus):
    return wittypid.WittyPi4Daemon(io.StringIO(SCHEDULE_YML), bus)


@pytest.fixture
def sc(local_tz):
    return ScheduleConfiguration(yaml.safe_load(SCHEDULE_YML))


def test_follows_schedule_across_midnight(daemon, bus, sc):
    """Run daemon and firmware for two days; every window must be powered, nothing else (#9)."""
    start = datetime.datetime(2025, 12, 8, 20, 0, tzinfo=UTC)  # 21:00 in Berlin
    end = start + datetime.timedelta(days=2)
    boots, shutdowns = [], []
    powered = True

    bus.now = start
    while bus.now < end:
        event = fake_firmware_tick(bus)
        if event == "startup" and not powered:
            powered = True
            bus.reg[wittypi4.I2C_ACTION_REASON] = ActionReason.ALARM_STARTUP.value
            boots.append(daemon.rtc_datetime)
        elif event == "shutdown" and powered:
            powered = False
            daemon._set_termination_alarms(sc)
            shutdowns.append(daemon.rtc_datetime)

        # daemon loop, every 60s; after the firmware, as it isn't aligned to the minute on a real system
        if powered and bus.now.second == 0:
            daemon._update_alarms(sc, daemon.rtc_datetime)

        bus.now += datetime.timedelta(seconds=1)

    starts = sorted({e.next_start(t) for e in sc.entries for t in (start, start + datetime.timedelta(days=1))
                     if e.next_start(t) < end})
    stops = {e.next_stop(t) for e in sc.entries for t in starts if e.next_start(t) == t and e.next_stop(t) < end}
    assert boots == starts
    # booted outside of the schedule at 21:00, so the first shutdown is the forced one
    assert shutdowns[0] == start + datetime.timedelta(seconds=wittypid.SHUTDOWN_DELAY_S)
    assert set(shutdowns[1:]) == stops


def test_update_alarms_when_active(daemon, bus, sc):
    bus.now = datetime.datetime(2025, 12, 8, 23, 30, tzinfo=UTC)  # 00:30 in Berlin
    now = daemon.rtc_datetime

    daemon._update_alarms(sc, now)

    assert daemon.get_shutdown_datetime() == sc.next_shutdown(now)
    assert daemon.get_startup_datetime() == sc.next_startup(now)


def test_update_alarms_when_inactive(daemon, bus, sc):
    bus.now = datetime.datetime(2025, 12, 8, 23, 30, 15, tzinfo=UTC) - datetime.timedelta(hours=1)  # 23:30 Berlin
    now = daemon.rtc_datetime

    daemon._update_alarms(sc, now)

    assert daemon.get_shutdown_datetime() == now + datetime.timedelta(seconds=wittypid.SHUTDOWN_DELAY_S)
    assert daemon.get_startup_datetime() == sc.next_startup(now)


@pytest.mark.parametrize(("reason", "shutdown"), [(ActionReason.ALARM_SHUTDOWN, True),
                                                   (ActionReason.LOW_VOLTAGE, True),
                                                   (ActionReason.ALARM_STARTUP, False)])
def test_update_alarms_after_shutdown_alarm(daemon, bus, sc, monkeypatch, reason, shutdown):
    calls = []
    monkeypatch.setattr(wittypid.os, "system", calls.append)
    bus.now = datetime.datetime(2025, 12, 8, 23, 30, tzinfo=UTC)  # active
    bus.reg[wittypi4.I2C_ACTION_REASON] = reason.value

    daemon._update_alarms(sc, daemon.rtc_datetime)

    assert calls == (["shutdown 0"] if shutdown else [])


def test_termination_sets_next_startup(daemon, bus, sc):
    bus.now = datetime.datetime(2025, 12, 8, 22, 0, 30, tzinfo=UTC)  # 23:00:30 in Berlin

    daemon._set_termination_alarms(sc)

    assert daemon.get_shutdown_datetime() is None
    assert daemon.get_startup_datetime() == datetime.datetime(2025, 12, 8, 23, 1, tzinfo=UTC)


# Startup checks


def test_run_exits_on_implausible_rtc(daemon, monkeypatch):
    monkeypatch.setattr(wittypid, "last_known_time", lambda: datetime.datetime(2030, 1, 1, tzinfo=UTC))
    with pytest.raises(SystemExit) as exc:
        daemon.run()
    assert exc.value.code == 3


def test_run_exits_on_rtc_sysclock_mismatch(daemon, monkeypatch):
    monkeypatch.setattr(wittypid, "last_known_time", lambda: datetime.datetime(2020, 1, 1, tzinfo=UTC))
    with pytest.raises(SystemExit) as exc:
        daemon.run()  # the fake RTC is in 2025
    assert exc.value.code == 3


# Clock sources


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Redirect the daemon's clock sources into tmp_path."""
    for name in ("FAKE_HWCLOCK_PATH", "TIMESYNC_CLOCK_PATH", "CHRONY_DRIFT_PATH"):
        path = getattr(wittypid, name)
        monkeypatch.setattr(wittypid, name, tmp_path / path.relative_to("/"))
    return tmp_path


def touch(path: pathlib.Path, ts: datetime.datetime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    os.utime(path, (ts.timestamp(), ts.timestamp()))


def test_fake_hwclock(root):
    (root / "etc").mkdir()
    (root / "etc/fake-hwclock.data").write_text("2025-12-08 21:30:00\n")

    assert wittypid.fake_hwclock() == datetime.datetime(2025, 12, 8, 21, 30, tzinfo=UTC)


def test_last_known_time_is_most_recent(root):
    (root / "etc").mkdir()
    (root / "etc/fake-hwclock.data").write_text("2025-12-08 21:30:00\n")
    timesync = datetime.datetime(2025, 12, 9, 6, 0, tzinfo=UTC)
    touch(root / "var/lib/systemd/timesync/clock", timesync)
    touch(root / "var/lib/chrony/chrony.drift", datetime.datetime(2025, 12, 1, tzinfo=UTC))

    assert wittypid.last_known_time() == timesync


def test_last_known_time_without_sources(root):
    with pytest.raises(RuntimeError):
        wittypid.last_known_time()
