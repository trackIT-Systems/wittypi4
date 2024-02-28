import enum
import datetime

import smbus2
import gpiozero

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


def bcd2bin(value):
    return value - 6 * (value >> 4)


def bin2bcd(value):
    return value + 6 * (value // 10)


class ActionReason(enum.Enum):
    REASON_ALARM1 = 0x01
    REASON_ALARM2 = 0x02
    REASON_CLICK = 0x03
    REASON_LOW_VOLTAGE = 0x04
    REASON_VOLTAGE_RESTORE = 0x05
    REASON_OVER_TEMPERATURE = 0x06
    REASON_BELOW_TEMPERATURE = 0x07
    REASON_ALARM1_DELAYED = 0x08
    REASON_USB_5V_CONNECTED = 0x09


class WittyPiException(Exception):
    pass


class WittyPi4(object):
    _instance = None

    def __init__(
        self,
        bus: smbus2.SMBus = smbus2.SMBus(1, force=True),
        addr: int = I2C_MC_ADDRESS,
        tz=datetime.UTC,
    ):
        self.bus = bus
        self.addr = addr
        self.tz = tz

        firmware_id = self.firmware_id
        if firmware_id != 0x26:
            raise WittyPiException("Unknown Firmware Id (got 0x%x, expected 0x26)" % firmware_id)

    # Read registers
    @property
    def firmware_id(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_ID)

    @property
    def voltage_in(self) -> float:
        return self.bus.read_byte_data(self.addr, I2C_VOLTAGE_IN_I) + (self.bus.read_byte_data(self.addr, I2C_VOLTAGE_IN_D) / 100)

    @property
    def voltage_out(self) -> float:
        return self.bus.read_byte_data(self.addr, I2C_VOLTAGE_OUT_I) + (self.bus.read_byte_data(self.addr, I2C_VOLTAGE_OUT_D) / 100)

    @property
    def current_out(self) -> float:
        return self.bus.read_byte_data(self.addr, I2C_CURRENT_OUT_I) + (self.bus.read_byte_data(self.addr, I2C_CURRENT_OUT_D) / 100)

    @property
    def watts_out(self) -> float:
        return self.voltage_out * self.current_out

    @property
    def power_ldo(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_POWER_MODE))

    @property
    def lv_shutdown(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_LV_SHUTDOWN))

    @property
    def alarm1_triggered(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_ALARM1_TRIGGERED))

    @property
    def alarm2_triggered(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_ALARM2_TRIGGERED))

    @property
    def action_reason(self) -> ActionReason:
        return ActionReason(self.bus.read_byte_data(self.addr, I2C_ACTION_REASON))

    @property
    def firmware_revision(self):
        return self.bus.read_byte_data(self.addr, I2C_FW_REVISION)

    # Configuration Registers
    @property
    def default_on(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_DEFAULT_ON))

    @default_on.setter
    def default_on(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_DEFAULT_ON, value)

    @property
    def pulse_interval(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_PULSE_INTERVAL)

    @pulse_interval.setter
    def pulse_interval(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_PULSE_INTERVAL, value)

    @property
    def lv_threshold(self) -> float:
        thres = self.bus.read_byte_data(self.addr, I2C_CONF_LOW_VOLTAGE)
        return 0.0 if (thres == 255) else (thres / 10)

    @lv_threshold.setter
    def lv_threshold(self, value: float):
        write_value = 255 if (value == 0.0) else int(value * 10)
        self.bus.write_byte_data(self.addr, I2C_CONF_LOW_VOLTAGE, write_value)

    @property
    def blink_led(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_BLINK_LED)

    @blink_led.setter
    def blink_led(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_BLINK_LED, value)

    @property
    def power_cut_delay(self) -> float:
        return self.bus.read_byte_data(self.addr, I2C_CONF_POWER_CUT_DELAY) / 10

    @power_cut_delay.setter
    def power_cut_delay(self, value: float):
        self.bus.write_byte_data(self.addr, I2C_CONF_BLINK_LED, int(value * 10))

    @property
    def recovery_voltage(self) -> float:
        thres = self.bus.read_byte_data(self.addr, I2C_CONF_RECOVERY_VOLTAGE)
        return 0.0 if (thres == 255) else (thres / 10)

    @recovery_voltage.setter
    def recovery_voltage(self, value: float):
        write_value = 255 if (value == 0.0) else int(value * 10)
        self.bus.write_byte_data(self.addr, I2C_CONF_RECOVERY_VOLTAGE, write_value)

    @property
    def dummy_load(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_DUMMY_LOAD)

    @dummy_load.setter
    def dummy_load(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_DUMMY_LOAD, value)

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
        return self._from_adj(self.bus.read_byte_data(self.addr, I2C_CONF_ADJ_VIN))

    @adj_vin.setter
    def adj_vin(self, value: float):
        write_value = self._to_adj(value)
        self.bus.write_byte_data(self.addr, I2C_CONF_ADJ_VIN, write_value)

    @property
    def adj_vout(self) -> float:
        return self._from_adj(self.bus.read_byte_data(self.addr, I2C_CONF_ADJ_VOUT))

    @adj_vout.setter
    def adj_vout(self, value: float):
        write_value = self._to_adj(value)
        self.bus.write_byte_data(self.addr, I2C_CONF_ADJ_VOUT, write_value)

    @property
    def adj_iout(self) -> float:
        return self._from_adj(self.bus.read_byte_data(self.addr, I2C_CONF_ADJ_IOUT))

    @adj_iout.setter
    def adj_iout(self, value: float):
        write_value = self._to_adj(value)
        self.bus.write_byte_data(self.addr, I2C_CONF_ADJ_IOUT, write_value)

    # Startup Alarm
    @property
    def alarm1_second(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_SECOND_ALARM1)

    @alarm1_second.setter
    def alarm1_second(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_SECOND_ALARM1, value)

    @property
    def alarm1_minute(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_MINUTE_ALARM1)

    @alarm1_minute.setter
    def alarm1_minute(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_MINUTE_ALARM1, value)

    @property
    def alarm1_hour(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_HOUR_ALARM1)

    @alarm1_hour.setter
    def alarm1_hour(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_HOUR_ALARM1, value)

    @property
    def alarm1_day(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_DAY_ALARM1)

    @alarm1_day.setter
    def alarm1_day(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_DAY_ALARM1, value)

    @property
    def alarm1_weekday(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_WEEKDAY_ALARM1)

    @alarm1_weekday.setter
    def alarm1_weekday(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_WEEKDAY_ALARM1, value)

    def set_startup_time(self, day: int, time: datetime.time):
        self.alarm1_day = day
        ts = time.astimezone(self.tz)
        self.alarm1_hour = ts.hour
        self.alarm1_minute = ts.minute
        self.alarm1_second = ts.second

    def get_startup_time(self) -> tuple[int, datetime.time]:
        ts = datetime.time(
            hour=self.alarm1_hour,
            minute=self.alarm1_minute,
            second=self.alarm1_second,
            tzinfo=self.tz,
        )
        return (self.alarm1_day, ts)

    def clear_startup_time(self):
        self.alarm1_day = 0
        self.alarm1_hour = 0
        self.alarm1_minute = 0
        self.alarm1_second = 0

    # Shutdown Alarm
    @property
    def alarm2_second(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_SECOND_ALARM2)

    @alarm2_second.setter
    def alarm2_second(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_SECOND_ALARM2, value)

    @property
    def alarm2_minute(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_MINUTE_ALARM2)

    @alarm2_minute.setter
    def alarm2_minute(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_MINUTE_ALARM2, value)

    @property
    def alarm2_hour(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_HOUR_ALARM2)

    @alarm2_hour.setter
    def alarm2_hour(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_HOUR_ALARM2, value)

    @property
    def alarm2_day(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_DAY_ALARM2)

    @alarm2_day.setter
    def alarm2_day(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_DAY_ALARM2, value)

    @property
    def alarm2_weekday(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_WEEKDAY_ALARM2)

    @alarm2_weekday.setter
    def alarm2_weekday(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_WEEKDAY_ALARM2, value)

    def set_shutdown_time(self, day: int, time: datetime.time):
        self.alarm2_day = day
        ts = time.astimezone(self.tz)
        self.alarm2_hour = ts.hour
        self.alarm2_minute = ts.minute
        self.alarm2_second = ts.second

    def get_shutdown_time(self) -> tuple[int, datetime.time]:
        ts = datetime.time(
            hour=self.alarm2_hour,
            minute=self.alarm2_minute,
            second=self.alarm2_second,
            tzinfo=self.tz,
        )
        return (self.alarm2_day, ts)

    def clear_shutdown_time(self):
        self.alarm2_day = 0
        self.alarm2_hour = 0
        self.alarm2_minute = 0
        self.alarm2_second = 0

    @property
    def rtc_offset(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_RTC_OFFSET)

    @rtc_offset.setter
    def rtc_offset(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_RTC_OFFSET, value)

    @property
    def rtc_tc(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_RTC_ENABLE_TC))

    @rtc_tc.setter
    def rtc_tc(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_RTC_ENABLE_TC, value)

    @property
    def alarm1_flag(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_FLAG_ALARM1))

    @alarm1_flag.setter
    def alarm1_flag(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_FLAG_ALARM1, value)

    @property
    def alarm2_flag(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_FLAG_ALARM2))

    @alarm2_flag.setter
    def alarm2_flag(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_FLAG_ALARM2, value)

    @property
    def ignore_power_mode(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_IGNORE_POWER_MODE))

    @ignore_power_mode.setter
    def ignore_power_mode(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_IGNORE_POWER_MODE, value)

    @property
    def ignore_lv_shutdown(self) -> bool:
        return bool(self.bus.read_byte_data(self.addr, I2C_CONF_IGNORE_LV_SHUTDOWN))

    @ignore_lv_shutdown.setter
    def ignore_lv_shutdown(self, value: bool):
        self.bus.write_byte_data(self.addr, I2C_CONF_IGNORE_LV_SHUTDOWN, value)

    @property
    def below_temperature_action(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_BELOW_TEMP_ACTION)

    @below_temperature_action.setter
    def below_temperature_action(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_BELOW_TEMP_ACTION, value)

    @property
    def below_temperature_threshold(self) -> int:
        value = self.bus.read_byte_data(self.addr, I2C_CONF_BELOW_TEMP_POINT)
        if value > 80:
            return value - 256
        else:
            return value

    @below_temperature_threshold.setter
    def below_temperature_threshold(self, value: int):
        if value < 0:
            value += 256
        self.bus.write_byte_data(self.addr, I2C_CONF_BELOW_TEMP_POINT, value)

    @property
    def over_temperature_action(self) -> int:
        return self.bus.read_byte_data(self.addr, I2C_CONF_OVER_TEMP_ACTION)

    @over_temperature_action.setter
    def over_temperature_action(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_OVER_TEMP_ACTION, value)

    @property
    def over_temperature_threshold(self) -> int:
        value = self.bus.read_byte_data(self.addr, I2C_CONF_OVER_TEMP_POINT)
        if value > 80:
            return value - 256
        else:
            return value

    @over_temperature_threshold.setter
    def over_temperature_threshold(self, value: int):
        if value < 0:
            value += 256
        self.bus.write_byte_data(self.addr, I2C_CONF_OVER_TEMP_POINT, value)

    @property
    def default_on_delay(self):
        return self.bus.read_byte_data(self.addr, I2C_CONF_DEFAULT_ON_DELAY)

    @default_on_delay.setter
    def default_on_delay(self, value: int):
        self.bus.write_byte_data(self.addr, I2C_CONF_DEFAULT_ON_DELAY, value)

    # LM75B Temperature Sensor
    # TODO: implement

    # RTC PCF85063
    @property
    def rtc_datetime(self) -> datetime.datetime:
        return datetime.datetime(
            year=2000 + bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_YEARS)),
            month=bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_MONTHS)),
            day=bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_DAYS)),
            hour=bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_HOURS)),
            minute=bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_MINUTES)),
            second=bcd2bin(self.bus.read_byte_data(self.addr, I2C_RTC_SECONDS)),
            tzinfo=self.tz,
        )

    @rtc_datetime.setter
    def rtc_datetime(self, value: datetime.datetime):
        ts = value.astimezone(self.tz)
        self.bus.write_byte_data(self.addr, I2C_RTC_YEARS, bin2bcd(ts.year-2000))
        self.bus.write_byte_data(self.addr, I2C_RTC_MONTHS, bin2bcd(ts.month))
        self.bus.write_byte_data(self.addr, I2C_RTC_WEEKDAYS, bin2bcd(ts.weekday()))
        self.bus.write_byte_data(self.addr, I2C_RTC_DAYS, bin2bcd(ts.day))
        self.bus.write_byte_data(self.addr, I2C_RTC_HOURS, bin2bcd(ts.hour))
        self.bus.write_byte_data(self.addr, I2C_RTC_MINUTES, bin2bcd(ts.minute))
        self.bus.write_byte_data(self.addr, I2C_RTC_SECONDS, bin2bcd(ts.second))

    def rtc_valid(self, threshold=datetime.timedelta(seconds=60)) -> bool:
        return abs(self.rtc_datetime - datetime.datetime.now(tz=self.tz)) < threshold
