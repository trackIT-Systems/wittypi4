import enum
import datetime
import logging
import platform
import time
import collections.abc

import astral
import astral.sun
import smbus2
import pytimeparse

logger = logging.getLogger("wittypi4")

# Device Adress
I2C_MC_ADDRESS = 0x08

# Read registers
I2C_ID = 0
I2C_VOLTAGE_IN_I = 1
I2C_VOLTAGE_IN_D = 2
I2C_VOLTAGE_OUT_I = 3
I2C_VOLTAGE_OUT_D = 4
I2C_CURRENT_OUT_I = 5
I2C_CURRENT_OUT_D = 6
I2C_POWER_MODE = 7
I2C_LV_SHUTDOWN = 8
I2C_ALARM1_TRIGGERED = 9
I2C_ALARM2_TRIGGERED = 10
I2C_ACTION_REASON = 11
I2C_FW_REVISION = 12

# Configuration registers
I2C_CONF_ADDRESS = 16
I2C_CONF_DEFAULT_ON = 17
I2C_CONF_PULSE_INTERVAL = 18
I2C_CONF_LOW_VOLTAGE = 19
I2C_CONF_BLINK_LED = 20
I2C_CONF_POWER_CUT_DELAY = 21
I2C_CONF_RECOVERY_VOLTAGE = 22
I2C_CONF_DUMMY_LOAD = 23
I2C_CONF_ADJ_VIN = 24
I2C_CONF_ADJ_VOUT = 25
I2C_CONF_ADJ_IOUT = 26

# Startup alarm
I2C_CONF_SECOND_ALARM1 = 27
I2C_CONF_MINUTE_ALARM1 = 28
I2C_CONF_HOUR_ALARM1 = 29
I2C_CONF_DAY_ALARM1 = 30
I2C_CONF_WEEKDAY_ALARM1 = 31

# Shutdown alarm
I2C_CONF_SECOND_ALARM2 = 32
I2C_CONF_MINUTE_ALARM2 = 33
I2C_CONF_HOUR_ALARM2 = 34
I2C_CONF_DAY_ALARM2 = 35
I2C_CONF_WEEKDAY_ALARM2 = 36

I2C_CONF_RTC_OFFSET = 37
I2C_CONF_RTC_ENABLE_TC = 38
I2C_CONF_FLAG_ALARM1 = 39
I2C_CONF_FLAG_ALARM2 = 40

I2C_CONF_IGNORE_POWER_MODE = 41
I2C_CONF_IGNORE_LV_SHUTDOWN = 42

I2C_CONF_BELOW_TEMP_ACTION = 43
I2C_CONF_BELOW_TEMP_POINT = 44
I2C_CONF_OVER_TEMP_ACTION = 45
I2C_CONF_OVER_TEMP_POINT = 46
I2C_CONF_DEFAULT_ON_DELAY = 47

I2C_LM75B_TEMPERATURE = 50
I2C_LM75B_CONF = 51
I2C_LM75B_THYST = 52
I2C_LM75B_TOS = 53

I2C_RTC_CTRL1 = 54
I2C_RTC_CTRL2 = 55
I2C_RTC_OFFSET = 56
I2C_RTC_RAM_BYTE = 57
I2C_RTC_SECONDS = 58
I2C_RTC_MINUTES = 59
I2C_RTC_HOURS = 60
I2C_RTC_DAYS = 61
I2C_RTC_WEEKDAYS = 62
I2C_RTC_MONTHS = 63
I2C_RTC_YEARS = 64
I2C_RTC_SECOND_ALARM = 65
I2C_RTC_MINUTE_ALARM = 66
I2C_RTC_HOUR_ALARM = 67
I2C_RTC_DAY_ALARM = 68
I2C_RTC_WEEKDAY_ALARM = 69
I2C_RTC_TIMER_VALUE = 70
I2C_RTC_TIMER_MODE = 71

# GPIO Pins
HALT_PIN = 4    # halt by GPIO-4 (BCM naming)
SYSUP_PIN = 17  # output SYS_UP signal on GPIO-17 (BCM naming)
CHRG_PIN = 5    # input to detect charging status
STDBY_PIN = 6   # input to detect standby status

# Values
ALARM_RESET = 80


def bcd2bin(value):
    return value - 6 * (value >> 4)


def bin2bcd(value):
    return value + 6 * (value // 10)


class ActionReason(enum.Enum):
    ALARM_STARTUP = 0x01
    ALARM_SHUTDOWN = 0x02
    BUTTON_CLICK = 0x03
    LOW_VOLTAGE = 0x04
    VOLTAGE_RESTORE = 0x05
    OVER_TEMPERATURE = 0x06
    BELOW_TEMPERATURE = 0x07
    ALARM_STARTUP_DELAYED = 0x08
    USB_5V_CONNECTED = 0x09


class WittyPiException(Exception):
    pass


class ScheduleEntry():
    def __init__(
            self,
            name: str,
            start: str,
            stop: str,
            location: astral.LocationInfo,
            tz: datetime.tzinfo = datetime.UTC,
            **kwargs,
    ):
        self.name = name
        self._start = start
        self._stop = stop
        self._tz = tz
        self._location = location

        if kwargs:
            logger.warning("Got unknown keywords %s, ignoring.", kwargs.keys())

        # test if schedule can be evaluated
        logger.debug("Schedule '%s' loaded, next_start: %s, next_stop: %s", self.name, self.next_stop(), self.next_start())

    def next_start(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return self.parse_timing(self._start, now=now)

    def next_stop(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return self.parse_timing(self._stop, now=now)

    def prev_start(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return self.parse_timing(self._start, forward=False, now=now)

    def prev_stop(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return self.parse_timing(self._stop, forward=False, now=now)

    def active(self, now: datetime.datetime | None = None) -> bool:
        return self.prev_start(now=now) > self.prev_stop(now=now)

    def parse_timing(self, time_str: str, day: int = 0, forward: bool = True, now: datetime.datetime = None):

        # initizalize now with datetime.now() if not set
        now = now or datetime.datetime.now(tz=self._tz)
        date = now.date() + datetime.timedelta(days=day)

        if "+" in time_str:
            ref, op, dur = time_str.partition("+")
            ref_ts = astral.sun.sun(self._location.observer, date=date, tzinfo=self._tz)[ref]
            offset = datetime.timedelta(seconds=pytimeparse.parse(dur, granularity="minutes"))
            ts = ref_ts + offset
        elif "-" in time_str:
            ref, op, dur = time_str.partition("-")
            ref_ts = astral.sun.sun(self._location.observer, date=date, tzinfo=self._tz)[ref]
            offset = datetime.timedelta(seconds=pytimeparse.parse(dur, granularity="minutes"))
            ts = ref_ts - offset
        else:
            # assume absolute time
            offset = datetime.timedelta(seconds=pytimeparse.parse(time_str, granularity="minutes"))
            ref_ts = datetime.datetime.combine(date, datetime.time(0, 0, 0), tzinfo=self._tz)
            ts = ref_ts + offset

        # evaluate parsed timestamp
        if forward:
            if ts <= now:
                # if timestamp is in the past or now, recurse with day+1
                return self.parse_timing(time_str, day+1, forward=forward, now=now)
            else:
                # return timestamp of the future
                return ts
        else:
            if ts > now:
                # if timestamp is in the future, recurse with day-1
                return self.parse_timing(time_str, day-1, forward=forward, now=now)
            else:
                # return timestamp of the past
                return ts

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r}, start={self._start!r}, stop={self._stop!r})"


class ButtonEntry(ScheduleEntry):
    def __init__(
        self,
        button_delay: datetime.timedelta | None,
        tz: datetime.tzinfo = datetime.UTC,
    ):
        self.button_delay = button_delay
        self._tz = tz

    @property
    def boot_ts(self):
        return datetime.datetime.now(tz=self._tz) - datetime.timedelta(seconds=time.monotonic())

    def prev_start(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return self.boot_ts

    def next_stop(self, now: datetime.datetime | None = None) -> datetime.datetime:
        if self.button_delay:
            return self.boot_ts + self.button_delay
        else:
            return None

    def next_start(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return None

    def prev_stop(self, now: datetime.datetime | None = None) -> datetime.datetime:
        return None

    def active(self, now: datetime.datetime | None = None) -> bool:
        now = now or datetime.datetime.now(tz=self._tz)
        next_stop = self.next_stop(now)
        if next_stop:
            return self.next_stop(now) > now
        else:
            return True

    def __repr__(self):
        return f"{self.__class__.__name__}(prev_start={self.prev_start()}, next_stop={self.next_stop()})"


class ScheduleConfiguration():

    def __init__(
        self,
        config: dict,
        tz: datetime.tzinfo = datetime.UTC,
    ):
        self._tz = tz

        logger.debug(config)

        # parsing location information
        self._location: astral.LocationInfo | None
        if ("lat" in config) and ("lon" in config):
            self._location = astral.LocationInfo(platform.node(), "", tz, config["lat"], config["lon"])
            logger.debug("Times relative to %s", self._location)
        else:
            self._location = None
            logger.warning("Schedule doesn't contain lat/lon information, relative schedules are disabled.")

        self.force_on: bool = False
        if "force_on" in config:
            if bool(config["force_on"]):
                self.force_on = True
                logger.info("Force on is enabled (%s)", config["force_on"])
            else:
                logger.debug("Force on is disabled (%s)", config["force_on"])

        try:
            self.button_delay = datetime.timedelta(seconds=pytimeparse.parse(config["button_delay"], granularity="minutes"))
        except Exception:
            self.button_delay = None
        logger.debug("Using button delay of %s", self.button_delay)

        self.entries: list[ScheduleEntry] = []

        if "schedule" not in config or not isinstance(config["schedule"], collections.abc.Iterable):
            logger.warning("Schedule missing in configuration, setting force_on.")
            self.force_on = True
        else:
            for entry_raw in config["schedule"]:
                try:
                    entry = ScheduleEntry(**entry_raw, location=self._location, tz=self._tz)
                    self.entries.append(entry)
                except AttributeError:
                    logger.warning("Schedule doesn't contain lat/lon information, ignoring %s", entry_raw)
            if not self.entries:
                logger.warning("No schedules found, setting force_on.")
                self.force_on = True

        logger.info("ScheduleConfiguration loaded - active: %s, next_shutdown: %s, next_startup: %s", self.active(), self.next_shutdown(), self.next_startup())
        for entry in self.entries:
            logger.info("%s", entry)

    def next_startup(self, now: datetime.datetime | None = None) -> datetime.datetime | None:
        now = now or datetime.datetime.now(tz=self._tz)
        # as all next_starts are in the future, pick the most recent start
        try:
            return min([e.next_start(now) for e in self.entries if e.next_start(now)])
        except ValueError:
            return None

    def next_shutdown(self, now: datetime.datetime | None = None) -> datetime.datetime | None:
        now = now or datetime.datetime.now(tz=self._tz)
        if self.force_on:
            return None

        try:
            next_ts = now
            while self.active(next_ts):
                next_ts = min([e.next_stop(next_ts) for e in self.entries if e.next_stop(next_ts) and e.next_stop(next_ts) > now])
                logger.debug("Next stop event would be %s, are we active then? %s", next_ts, self.active(next_ts))

                if next_ts - now >= datetime.timedelta(days=1):
                    logger.debug("No shutdown required, we are online for over 1 day")
                    return None

            return next_ts

        except ValueError:
            return None

    def active(self, now: datetime.datetime | None = None):
        now = now or datetime.datetime.now(tz=self._tz)
        return self.force_on or any([e.active(now) for e in self.entries])


class WittyPi4(object):
    def __init__(
        self,
        bus: smbus2.SMBus | None = None,
        addr: int = I2C_MC_ADDRESS,
        tz=datetime.UTC,
    ):

        self._bus = bus or smbus2.SMBus(1, force=True)
        self._addr = addr
        self._tz = tz

        try:
            firmware_id = self.firmware_id
            if firmware_id != 0x26:
                raise WittyPiException("unknown Firmware Id (got 0x%x, expected 0x26)" % firmware_id)
        except OSError as ex:
            raise WittyPiException("error reading address 0x%x, check device connection" % self._addr) from ex

        logger.debug("WittyPi 4 probed successfully")

    def __del__(self):
        self._bus.close()

    # Read registers
    @property
    def firmware_id(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_ID)

    @property
    def voltage_in(self) -> float:
        return self._bus.read_byte_data(self._addr, I2C_VOLTAGE_IN_I) + (self._bus.read_byte_data(self._addr, I2C_VOLTAGE_IN_D) / 100)

    @property
    def voltage_out(self) -> float:
        return self._bus.read_byte_data(self._addr, I2C_VOLTAGE_OUT_I) + (self._bus.read_byte_data(self._addr, I2C_VOLTAGE_OUT_D) / 100)

    @property
    def current_out(self) -> float:
        return self._bus.read_byte_data(self._addr, I2C_CURRENT_OUT_I) + (self._bus.read_byte_data(self._addr, I2C_CURRENT_OUT_D) / 100)

    @property
    def watts_out(self) -> float:
        return self.voltage_out * self.current_out

    @property
    def power_ldo(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_POWER_MODE))

    @property
    def lv_shutdown(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_LV_SHUTDOWN))

    @property
    def alarm1_triggered(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_ALARM1_TRIGGERED))

    @property
    def alarm2_triggered(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_ALARM2_TRIGGERED))

    @property
    def action_reason(self) -> ActionReason:
        return ActionReason(self._bus.read_byte_data(self._addr, I2C_ACTION_REASON))

    @property
    def firmware_revision(self):
        return self._bus.read_byte_data(self._addr, I2C_FW_REVISION)

    # Configuration Registers
    @property
    def default_on(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_DEFAULT_ON))

    @default_on.setter
    def default_on(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_DEFAULT_ON, value)

    @property
    def pulse_interval(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_PULSE_INTERVAL)

    @pulse_interval.setter
    def pulse_interval(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_PULSE_INTERVAL, value)

    @property
    def lv_threshold(self) -> float:
        thres = self._bus.read_byte_data(self._addr, I2C_CONF_LOW_VOLTAGE)
        return 0.0 if (thres == 255) else (thres / 10)

    @lv_threshold.setter
    def lv_threshold(self, value: float):
        write_value = 255 if (value == 0.0) else int(value * 10)
        self._bus.write_byte_data(self._addr, I2C_CONF_LOW_VOLTAGE, write_value)

    @property
    def blink_led(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_BLINK_LED)

    @blink_led.setter
    def blink_led(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_BLINK_LED, value)

    @property
    def power_cut_delay(self) -> float:
        return self._bus.read_byte_data(self._addr, I2C_CONF_POWER_CUT_DELAY) / 10

    @power_cut_delay.setter
    def power_cut_delay(self, value: float):
        self._bus.write_byte_data(self._addr, I2C_CONF_BLINK_LED, int(value * 10))

    @property
    def recovery_voltage(self) -> float:
        thres = self._bus.read_byte_data(self._addr, I2C_CONF_RECOVERY_VOLTAGE)
        return 0.0 if (thres == 255) else (thres / 10)

    @recovery_voltage.setter
    def recovery_voltage(self, value: float):
        write_value = 255 if (value == 0.0) else int(value * 10)
        self._bus.write_byte_data(self._addr, I2C_CONF_RECOVERY_VOLTAGE, write_value)

    @property
    def dummy_load(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_DUMMY_LOAD)

    @dummy_load.setter
    def dummy_load(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_DUMMY_LOAD, value)

    @staticmethod
    def _from_adj(value: int) -> float:
        if value > 127:
            return (value - 255) / 100
        else:
            return value / 100

    @staticmethod
    def _to_adj(value: float) -> int:
        value = int(value * 100)
        if value < 0:
            return value + 255
        else:
            return value

    @property
    def adj_vin(self) -> float:
        return self._from_adj(self._bus.read_byte_data(self._addr, I2C_CONF_ADJ_VIN))

    @adj_vin.setter
    def adj_vin(self, value: float):
        write_value = self._to_adj(value)
        self._bus.write_byte_data(self._addr, I2C_CONF_ADJ_VIN, write_value)

    @property
    def adj_vout(self) -> float:
        return self._from_adj(self._bus.read_byte_data(self._addr, I2C_CONF_ADJ_VOUT))

    @adj_vout.setter
    def adj_vout(self, value: float):
        write_value = self._to_adj(value)
        self._bus.write_byte_data(self._addr, I2C_CONF_ADJ_VOUT, write_value)

    @property
    def adj_iout(self) -> float:
        return self._from_adj(self._bus.read_byte_data(self._addr, I2C_CONF_ADJ_IOUT))

    @adj_iout.setter
    def adj_iout(self, value: float):
        write_value = self._to_adj(value)
        self._bus.write_byte_data(self._addr, I2C_CONF_ADJ_IOUT, write_value)

    # Startup Alarm
    @property
    def alarm1_second(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_SECOND_ALARM1))

    @alarm1_second.setter
    def alarm1_second(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_SECOND_ALARM1, bin2bcd(value))

    @property
    def alarm1_minute(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_MINUTE_ALARM1))

    @alarm1_minute.setter
    def alarm1_minute(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_MINUTE_ALARM1, bin2bcd(value))

    @property
    def alarm1_hour(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_HOUR_ALARM1))

    @alarm1_hour.setter
    def alarm1_hour(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_HOUR_ALARM1, bin2bcd(value))

    @property
    def alarm1_day(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_DAY_ALARM1))

    @alarm1_day.setter
    def alarm1_day(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_DAY_ALARM1, bin2bcd(value))

    @property
    def alarm1_weekday(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_WEEKDAY_ALARM1))

    @alarm1_weekday.setter
    def alarm1_weekday(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_WEEKDAY_ALARM1, bin2bcd(value))

    @property
    def alarm2_second(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_SECOND_ALARM2))

    @alarm2_second.setter
    def alarm2_second(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_SECOND_ALARM2, bin2bcd(value))

    @property
    def alarm2_minute(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_MINUTE_ALARM2))

    @alarm2_minute.setter
    def alarm2_minute(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_MINUTE_ALARM2, bin2bcd(value))

    @property
    def alarm2_hour(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_HOUR_ALARM2))

    @alarm2_hour.setter
    def alarm2_hour(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_HOUR_ALARM2, bin2bcd(value))

    @property
    def alarm2_day(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_DAY_ALARM2))

    @alarm2_day.setter
    def alarm2_day(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_DAY_ALARM2, bin2bcd(value))

    @property
    def alarm2_weekday(self) -> int:
        return bcd2bin(self._bus.read_byte_data(self._addr, I2C_CONF_WEEKDAY_ALARM2))

    @alarm2_weekday.setter
    def alarm2_weekday(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_WEEKDAY_ALARM2, bin2bcd(value))

    # High level interface for alarms
    def _timer_next_ts(self, day: int, weekday: int, hour: int, minute: int, second: int) -> None | datetime.datetime:
        ts = self.rtc_datetime

        # if all register are unset, return None
        if (day == ALARM_RESET) and (weekday == ALARM_RESET) and (hour == ALARM_RESET) and (minute == ALARM_RESET) and (second == ALARM_RESET):
            return None
        if (day == 0):
            return None

        logger.debug("Iterating %s to match day %02i %02i:%02i:%02i", ts, day, hour, minute, second)

        # get current date and iterate until day matches
        while (second != ts.second) and (second != ALARM_RESET):
            ts += datetime.timedelta(seconds=1)
        while (minute != ts.minute) and (minute != ALARM_RESET):
            ts += datetime.timedelta(minutes=1)
        while (hour != ts.hour) and (hour != ALARM_RESET):
            ts += datetime.timedelta(hours=1)
        while (weekday != ts.weekday()) and (weekday != ALARM_RESET):
            ts += datetime.timedelta(days=1)
        while (day != ts.day) and (day != ALARM_RESET):
            ts += datetime.timedelta(days=1)

        return ts

    def set_startup_datetime(self, ts: datetime.datetime | None):
        if ts is None:
            self.alarm1_day = ALARM_RESET
            self.alarm1_weekday = ALARM_RESET
            self.alarm1_hour = ALARM_RESET
            self.alarm1_minute = ALARM_RESET
            self.alarm1_second = ALARM_RESET
            return

        ts = ts.astimezone(self._tz)
        if ts < self.rtc_datetime:
            logger.warning("startup time is in the past.")

        self.alarm1_day = ts.day
        self.alarm1_weekday = ALARM_RESET
        self.alarm1_hour = ts.hour
        self.alarm1_minute = ts.minute
        self.alarm1_second = ts.second

    def get_startup_datetime(self) -> datetime.datetime | None:
        return self._timer_next_ts(
            day=self.alarm1_day,
            weekday=self.alarm1_weekday,
            hour=self.alarm1_hour,
            minute=self.alarm1_minute,
            second=self.alarm1_second,
        )

    def set_shutdown_datetime(self, ts: datetime.datetime | None):
        if ts is None:
            self.alarm2_day = ALARM_RESET
            self.alarm2_weekday = ALARM_RESET
            self.alarm2_hour = ALARM_RESET
            self.alarm2_minute = ALARM_RESET
            self.alarm2_second = ALARM_RESET
            return

        ts = ts.astimezone(self._tz)
        if ts < self.rtc_datetime:
            logger.warning("startup time is in the past.")

        self.alarm2_day = ts.day
        self.alarm2_weekday = ALARM_RESET       # ignore weekday in this mode
        self.alarm2_hour = ts.hour
        self.alarm2_minute = ts.minute
        self.alarm2_second = ts.second

    def get_shutdown_datetime(self) -> datetime.datetime | None:
        return self._timer_next_ts(
            day=self.alarm2_day,
            weekday=self.alarm2_weekday,
            hour=self.alarm2_hour,
            minute=self.alarm2_minute,
            second=self.alarm2_second,
        )

    @property
    def rtc_offset(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_RTC_OFFSET)

    @rtc_offset.setter
    def rtc_offset(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_RTC_OFFSET, value)

    @property
    def rtc_tc(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_RTC_ENABLE_TC))

    @rtc_tc.setter
    def rtc_tc(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_RTC_ENABLE_TC, value)

    @property
    def alarm1_flag(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_FLAG_ALARM1))

    @alarm1_flag.setter
    def alarm1_flag(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_FLAG_ALARM1, value)

    @property
    def alarm2_flag(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_FLAG_ALARM2))

    @alarm2_flag.setter
    def alarm2_flag(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_FLAG_ALARM2, value)

    @property
    def ignore_power_mode(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_IGNORE_POWER_MODE))

    @ignore_power_mode.setter
    def ignore_power_mode(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_IGNORE_POWER_MODE, value)

    @property
    def ignore_lv_shutdown(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, I2C_CONF_IGNORE_LV_SHUTDOWN))

    @ignore_lv_shutdown.setter
    def ignore_lv_shutdown(self, value: bool):
        self._bus.write_byte_data(self._addr, I2C_CONF_IGNORE_LV_SHUTDOWN, value)

    @property
    def below_temperature_action(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_BELOW_TEMP_ACTION)

    @below_temperature_action.setter
    def below_temperature_action(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_BELOW_TEMP_ACTION, value)

    @property
    def below_temperature_threshold(self) -> int:
        value = self._bus.read_byte_data(self._addr, I2C_CONF_BELOW_TEMP_POINT)
        if value > 80:
            return value - 256
        else:
            return value

    @below_temperature_threshold.setter
    def below_temperature_threshold(self, value: int):
        if value < 0:
            value += 256
        self._bus.write_byte_data(self._addr, I2C_CONF_BELOW_TEMP_POINT, value)

    @property
    def over_temperature_action(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_CONF_OVER_TEMP_ACTION)

    @over_temperature_action.setter
    def over_temperature_action(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_OVER_TEMP_ACTION, value)

    @property
    def over_temperature_threshold(self) -> int:
        value = self._bus.read_byte_data(self._addr, I2C_CONF_OVER_TEMP_POINT)
        if value > 80:
            return value - 256
        else:
            return value

    @over_temperature_threshold.setter
    def over_temperature_threshold(self, value: int):
        if value < 0:
            value += 256
        self._bus.write_byte_data(self._addr, I2C_CONF_OVER_TEMP_POINT, value)

    @property
    def default_on_delay(self):
        return self._bus.read_byte_data(self._addr, I2C_CONF_DEFAULT_ON_DELAY)

    @default_on_delay.setter
    def default_on_delay(self, value: int):
        self._bus.write_byte_data(self._addr, I2C_CONF_DEFAULT_ON_DELAY, value)

    # LM75B Temperature Sensor
    @staticmethod
    def _lm75b_celsius(data):
        return int.from_bytes(data.to_bytes(2, "little"), signed=True) / 256

    @property
    def lm75b_temperature(self):
        return self._lm75b_celsius(self._bus.read_word_data(self._addr, I2C_LM75B_TEMPERATURE))

    # RTC PCF85063
    @property
    def rtc_datetime(self) -> datetime.datetime:
        return datetime.datetime(
            year=2000 + bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_YEARS)),
            month=bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_MONTHS)),
            day=bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_DAYS)),
            hour=bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_HOURS)),
            minute=bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_MINUTES)),
            second=bcd2bin(self._bus.read_byte_data(self._addr, I2C_RTC_SECONDS)),
            tzinfo=self._tz,
        )

    @rtc_datetime.setter
    def rtc_datetime(self, value: datetime.datetime):
        ts = value.astimezone(self._tz)
        self._bus.write_byte_data(self._addr, I2C_RTC_YEARS, bin2bcd(ts.year-2000))
        self._bus.write_byte_data(self._addr, I2C_RTC_MONTHS, bin2bcd(ts.month))
        self._bus.write_byte_data(self._addr, I2C_RTC_WEEKDAYS, bin2bcd(ts.weekday()))
        self._bus.write_byte_data(self._addr, I2C_RTC_DAYS, bin2bcd(ts.day))
        self._bus.write_byte_data(self._addr, I2C_RTC_HOURS, bin2bcd(ts.hour))
        self._bus.write_byte_data(self._addr, I2C_RTC_MINUTES, bin2bcd(ts.minute))
        self._bus.write_byte_data(self._addr, I2C_RTC_SECONDS, bin2bcd(ts.second))

    @property
    def rtc_ctrl1(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_RTC_CTRL1)

    @property
    def rtc_ctrl2(self) -> int:
        return self._bus.read_byte_data(self._addr, I2C_RTC_CTRL2)

    def rtc_ctrl2_clear_alarm(self):
        ctrl2_value = self._bus.read_byte_data(self._addr, I2C_RTC_CTRL2)
        ctrl2_value &= 0b10111111
        self._bus.write_byte_data(self._addr, I2C_RTC_CTRL2, ctrl2_value)

    def clear_flags(self):
        self.rtc_ctrl2_clear_alarm()
        self.alarm1_flag = False
        self.alarm2_flag = False

    def rtc_sysclock_match(self, threshold=datetime.timedelta(seconds=2)) -> bool:
        return abs(self.rtc_datetime - datetime.datetime.now(tz=self._tz)) < threshold

    def dump_config(self) -> dict:
        return {
            prop: getattr(self, prop)
            for prop in dir(self)
            if not (prop.startswith("_") or callable(getattr(self, prop)))
        }

    def get_status(self) -> dict[str, float | int]:
        return {
            "Id": self.firmware_id,
            "Input Voltage (V)": self.voltage_in,
            "Output Voltage (V)": self.voltage_out,
            "Output Current (A)": self.current_out,
            "Power Mode": self.power_ldo,
            "Revision": self.firmware_revision,
            "Temperature (°C)": self.lm75b_temperature,
        }
