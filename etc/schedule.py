import datetime
import logging

from wittypi4 import ScheduleConfiguration

logging.basicConfig(level=logging.INFO)

schedule = [
    dict(
        name="s1",
        start="00:00",
        stop="02:00",
    ),
    dict(
        name="s2",
        start="01:00",
        stop="05:00",
    ),
    dict(
        name="s3",
        start="03:00",
        stop="04:00",
    ),
    dict(
        name="s4",
        start="05:00",
        stop="23:59",
    ),
]

sc = ScheduleConfiguration(dict(
    lat=50.85318,
    lon=8.78735,
    force_on=False,
    button_delay="00:30",
    schedule=schedule,
))

tests = [
    datetime.datetime(2024, 1, 1, 0, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 0, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 1, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 2, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 3, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 4, 30, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 5, 00, 0, tzinfo=datetime.UTC),
    datetime.datetime(2024, 1, 1, 5, 30, 0, tzinfo=datetime.UTC),
]

for ts in tests:
    logging.info("%s: next_startup: %s, next_shutdown: %s, active: %s", ts, sc.next_startup(ts), sc.next_shutdown(ts), sc.active(ts))
