#!/usr/bin/env python3

import logging
import signal
import time
import threading

import smbus2

from . import WittyPi4
from .__main__ import parser

parser.prog = "wittypid"
parser.usage = "daemon to configure and handle WittyPi schedules"

logger = logging.getLogger(parser.prog)


class WittyPi4Daemon(WittyPi4, threading.Thread):
    def __init__(self, *args, **kwargs):
        self._running = False
        super().__init__(*args, **kwargs)

    def terminate(self, sig):
        logger.warning("Caught %s, terminating.", signal.Signals(sig).name)
        self._running = False

    def run(self):
        self._running = True

        signal.signal(signal.SIGINT, lambda sig, _: self.terminate(sig))
        signal.signal(signal.SIGTERM, lambda sig, _: self.terminate(sig))

        logger.info("Welcome to %s, RTC: %s, action reason: %s", parser.prog, self.rtc_datetime, self.action_reason)
        logger.info("Sheduled shutdown: %s", self.get_shutdown_datetime())
        self.clear_flags()

        while self._running:
            time.sleep(1)

        logger.info("Bye from %s, RTC: %s, action reason: %s", parser.prog, self.rtc_datetime, self.action_reason)
        logger.info("Sheduled startup: %s", self.get_startup_datetime())


def main():
    args = parser.parse_args()

    # configure logging
    logging_level = max(0, logging.WARN - (args.verbose * 10))
    logging_stderr = logging.StreamHandler()
    logging_stderr.setLevel(logging_level)
    logging.basicConfig(level=logging.DEBUG, handlers=[logging_stderr])

    # setup wittypi
    bus = smbus2.SMBus(bus=args.bus, force=args.force)
    wp = WittyPi4Daemon(bus, args.addr)

    wp.run()


if __name__ == "__main__":
    main()
