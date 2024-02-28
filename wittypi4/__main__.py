import logging
import argparse
import datetime

import smbus2

from . import WittyPi4

logger = logging.getLogger("wittypi4")

parser = argparse.ArgumentParser(
    "wittypi4",
    description='Control WittyPi 4 devices',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="count", default=0)

parser.add_argument("--force", help="force I2C bus access, required when using with RTC kernel module", default=True, action=argparse.BooleanOptionalAction)
parser.add_argument("--bus", help="I2C bus to be used", default=1, type=int)
parser.add_argument("--addr", help="WittyPi I2C address", default=8, type=int)


if __name__ == "__main__":
    args = parser.parse_args()

    # configure logging
    logging_level = max(0, logging.WARN - (args.verbose * 10))
    logging_stderr = logging.StreamHandler()
    logging_stderr.setLevel(logging_level)
    logging.basicConfig(level=logging.DEBUG, handlers=[logging_stderr])

    # setup wittypi
    bus = smbus2.SMBus(bus=args.bus, force=args.force)
    wp = WittyPi4(bus, args.addr)

    if logging_level <= logging.DEBUG:
        for prop, val in wp.dump_config().items():
            logger.debug("%s: %s", prop, val)

    # print status information
    logger.info("System Time:  %s", datetime.datetime.now())
    logger.info("WittyPi Time: %s", wp.rtc_datetime)
    logger.info("Startup Reason: %s", wp.action_reason)
    logger.info("Power Usage: %.2f V -> %.2f V, %.2f A (%.2f W)", wp.voltage_in, wp.voltage_out, wp.current_out, wp.watts_out)

    wp.alarm1_flag = False
    wp.alarm2_flag = False

    shutdown = wp.rtc_datetime + datetime.timedelta(seconds=5)
    startup = wp.rtc_datetime + datetime.timedelta(seconds=25)
    logger.info("Scheduling shutdown @%s", shutdown)
    wp.set_shutdown_datetime(shutdown)
    logger.info("Scheduling startup @%s", startup)
    wp.set_startup_datetime(startup)

    logger.info("Next Startup: %s", wp.get_startup_datetime())
    logger.info("Next Shutdown: %s", wp.get_shutdown_datetime())

    logger.info("RTC Control 1: %s", format(wp.rtc_ctrl1, '08b'))
    logger.info("RTC Control 2: %s", format(wp.rtc_ctrl2, '08b'))
    logger.info("Flag Alarm 1: %s", wp.alarm1_flag)
    logger.info("Flag Alarm 2: %s", wp.alarm2_flag)
    # logger.info("RTC Control 2: %b", wp.rtc_ctrl2)
