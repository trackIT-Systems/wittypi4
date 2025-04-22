#!/usr/bin/env python3

import argparse
import datetime
import io
import logging
import os
import pathlib
import signal
import threading
import time

import smbus2
import yaml

from . import ActionReason, ButtonEntry, ScheduleConfiguration, WittyPi4, WittyPiException
from .__main__ import parser

parser.prog = "wittypid"
parser.usage = "daemon to configure and handle WittyPi schedules"
parser.add_argument(
    "-s", "--schedule", type=argparse.FileType("r"), help="YML schedule configuration", default="schedule.yml"
)

logger = logging.getLogger(parser.prog)


def fake_hwclock() -> datetime.datetime:
    path = pathlib.Path("/etc/fake-hwclock.data")
    with path.open(encoding="ascii") as fp:
        data = fp.read()

    ts = datetime.datetime.strptime(data, "%Y-%m-%d %H:%M:%S\n").astimezone(datetime.UTC)
    logger.info("Read fake_hwclock: %s", ts)
    return ts


class WittyPi4Daemon(WittyPi4, threading.Thread):
    def __init__(self, schedule: io.TextIOWrapper, *args, **kwargs):
        self._stop = threading.Event()
        self._schedule = schedule
        super().__init__(*args, **kwargs)

    def terminate(self, sig):
        logger.warning("Caught %s, terminating.", signal.Signals(sig).name)
        self._stop.set()

    def run(self):
        signal.signal(signal.SIGINT, lambda sig, _: self.terminate(sig))
        signal.signal(signal.SIGTERM, lambda sig, _: self.terminate(sig))

        logger.info("Welcome to %s, action reason: %s", parser.prog, self.action_reason)
        self.clear_flags()

        # setting default on
        self.default_on = True
        self.default_on_delay = 1

        # setting power cut delay
        self.power_cut_delay = 30

        try:
            # check clock plausibility
            if self.rtc_datetime < fake_hwclock():
                logger.warning(
                    "RTC is implausible (%s). Connect to GPS/internet and wait for timesync", self.rtc_datetime
                )
                exit(3)

            # check RTC and systemclock matching
            if not self.rtc_sysclock_match():
                logger.warning("RTC is does not match system clock, check system configuration")
                exit(3)

            # set clock synced
            sync_path = pathlib.Path("/run/systemd/timesync/synchronized")
            logger.info("RTC is valid, setting %s", sync_path)
            while not sync_path.parent.exists():
                logger.info("Waiting for /run/systemd/timesync/...")
                time.sleep(1)
            sync_path.touch()
        except ValueError:
            logger.error("RTC is unset. Connect to GPS/internet, and wait for timesync")
            exit(3)

        # read schedule configuration
        schedule_raw: dict = yaml.safe_load(self._schedule)
        sc = ScheduleConfiguration(schedule_raw)

        if self.action_reason in [ActionReason.BUTTON_CLICK, ActionReason.VOLTAGE_RESTORE]:
            button_entry = ButtonEntry(sc.button_delay)
            logger.info("Started by %s, adding %s", self.action_reason, button_entry)
            sc.entries.append(button_entry)

        shutdown_delay_s = 30

        while not self._stop.is_set():
            now = self.rtc_datetime
            next_startup = sc.next_startup(now)
            next_shutdown = sc.next_shutdown(now)

            logger.info("Setting next_shutdown: %s, next_startup: %s", next_shutdown, next_startup)
            self.set_startup_datetime(next_startup)
            self.set_shutdown_datetime(next_shutdown)

            # somehow we're here while should't be active, setting shutdown with delay
            if not sc.active(now):
                logger.info("Shouldn't be active, scheduling shutdown in %ss", shutdown_delay_s)
                self.set_shutdown_datetime(self.rtc_datetime + datetime.timedelta(seconds=shutdown_delay_s))

            # somehow the shutdown alarm fired, and we're still running.
            elif self.action_reason in [
                ActionReason.ALARM_SHUTDOWN,
                ActionReason.LOW_VOLTAGE,
                ActionReason.OVER_TEMPERATURE,
            ]:
                logger.warning("Alarm %s fired, shutting down", self.action_reason)
                os.system("shutdown 0")

            # wait for 60s or until signal
            self._stop.wait(60)

        self.set_shutdown_datetime(None)
        self.set_startup_datetime(sc.next_startup())
        logger.info(
            "Terminating, set ScheduleConfiguration shutdown: %s, startup: %s",
            self.get_shutdown_datetime(),
            self.get_startup_datetime(),
        )
        logger.info("Bye from wittypid")


def main():
    args = parser.parse_args()

    # configure logging
    logging_level = max(0, logging.WARN - (args.verbose * 10))
    logging_stderr = logging.StreamHandler()
    logging_stderr.setLevel(logging_level)
    logging.basicConfig(level=logging.DEBUG, handlers=[logging_stderr])

    # setup wittypi
    bus = smbus2.SMBus(bus=args.bus, force=args.force)
    try:
        wp = WittyPi4Daemon(args.schedule, bus, args.addr)
    except WittyPiException as ex:
        logger.error("Couldn't connect to WittyPi (%s), terminating.", ex)
        exit(1)

    wp.run()


if __name__ == "__main__":
    main()
