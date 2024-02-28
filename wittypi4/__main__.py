import logging

from . import WittyPi4

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("wittypid")

if __name__ == "__main__":
    wp = WittyPi4()

    for prop in dir(wp):
        if prop.startswith("_"):
            continue

        val = getattr(wp, prop)
        if callable(val):
            continue

        logger.info("%s: %s", prop, getattr(wp, prop))

    logger.info(wp.get_shutdown_time())
    logger.info(wp.get_startup_time())
