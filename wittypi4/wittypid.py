#!/usr/bin/env python3

import logging
import signal
import time
import threading
import argparse
import io
import datetime
import pathlib

import smbus2

from . import WittyPi4, ScheduleConfiguration, ActionReason, ButtonEntry, WittyPiException
from .__main__ import parser

parser.prog = "wittypid"
parser.usage = "daemon to configure and handle WittyPi schedules"
parser.add_argument("-s", "--schedule", type=argparse.FileType('r'), help="ONNX model", default="schedule.yml")

logger = logging.getLogger(parser.prog)


def fake_hwclock() -> datetime.datetime:
    path = pathlib.Path("/etc/fake-hwclock.data")
    with path.open(encoding="ascii") as fp:
        data = fp.read()

    ts = datetime.datetime.strptime(data, '%Y-%m-%d %H:%M:%S\n').astimezone(datetime.UTC)
    logger.info("Read fake_hwclock: %s", ts)
    return ts


class WittyPi4Daemon(WittyPi4, threading.Thread):
    def __init__(self, schedule: io.TextIOWrapper, *args, **kwargs):
        self._running = False
        self._schedule = schedule
        super().__init__(*args, **kwargs)

    def terminate(self, sig):
        logger.warning("Caught %s, terminating.", signal.Signals(sig).name)
        self._running = False

    def run(self):
        self._running = True

        signal.signal(signal.SIGINT, lambda sig, _: self.terminate(sig))
        signal.signal(signal.SIGTERM, lambda sig, _: self.terminate(sig))

        logger.info("Welcome to %s, action reason: %s", parser.prog, self.action_reason)
        self.clear_flags()

        # setting default on
        self.default_on = True
        self.default_on_delay = 1

        try:
            # check clock plausibility
            if self.rtc_datetime < fake_hwclock():
                logger.warning("RTC is implausible (%s). Connect to GPS/internet and wait for timesync", self.rtc_datetime)
                exit(3)

            # check RTC and systemclock matching
            if not self.rtc_sysclock_match():
                logger.warning("RTC is does not match system clock, check system configuration")
                exit(3)

            # set clock synced
            sync_path = pathlib.Path("/run/systemd/timesync/synchronized")
            logger.info("RTC is valid, setting %s", sync_path)
            sync_path.parent.mkdir(exist_ok=True)
            sync_path.touch()
        except ValueError:
            logger.error("RTC is unset. Connect to GPS/internet, and wait for timesync")
            exit(3)

        # read schedule configuration
        sc = ScheduleConfiguration(self._schedule, self._tz)
        if self.action_reason == ActionReason.BUTTON_CLICK:
            button_entry = ButtonEntry(sc.button_delay)
            logger.info("Started by Button, adding %s", button_entry)
            sc.entries.append(button_entry)

        logger.info("Setting ScheduleConfiguration shutdown: %s, startup: %s", sc.next_shutdown, sc.next_startup)
        self.set_shutdown_datetime(sc.next_shutdown)
        self.set_startup_datetime(sc.next_startup)

        if not sc.active:
            delay = datetime.timedelta(seconds=10)
            logger.info("Shouldn't be active, scheduling shutdown in %ss", delay.total_seconds())
            self.set_shutdown_datetime(self.rtc_datetime + delay)

        while self._running:
            time.sleep(1)

        logger.info("Bye from %s, RTC: %s, action reason: %s", parser.prog, self.rtc_datetime, self.action_reason)
        logger.info("Resetting shutdown schedule")
        self.set_shutdown_datetime(None)


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
