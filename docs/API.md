# WittyPi 4 Python API Reference

This document provides comprehensive API reference for developers using the WittyPi 4 Python library.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Core Classes](#core-classes)
  - [WittyPi4](#wittypi4)
  - [ScheduleConfiguration](#scheduleconfiguration)
  - [ActionReason](#actionreason)
- [Hardware Monitoring](#hardware-monitoring)
- [Schedule Management](#schedule-management)
- [Alarm Configuration](#alarm-configuration)
- [RTC Operations](#rtc-operations)
- [Configuration Properties](#configuration-properties)
- [Constants Reference](#constants-reference)
- [Exception Handling](#exception-handling)

## Quick Start

```python
import smbus2
from wittypi4 import WittyPi4
import datetime

# Initialize WittyPi 4
bus = smbus2.SMBus(1, force=True)
wp = WittyPi4(bus)

# Read hardware status
print(f"Input Voltage: {wp.voltage_in}V")
print(f"Output Voltage: {wp.voltage_out}V")
print(f"Current: {wp.current_out}A")
print(f"Temperature: {wp.lm75b_temperature}°C")
print(f"RTC Time: {wp.rtc_datetime}")
print(f"Startup Reason: {wp.action_reason}")

# Schedule next startup in 1 hour
wp.set_startup_datetime(datetime.datetime.now() + datetime.timedelta(hours=1))

# Schedule shutdown in 30 minutes
wp.set_shutdown_datetime(datetime.datetime.now() + datetime.timedelta(minutes=30))
```

## Installation

```bash
# Using pip
pip install -e .

# Using pdm
pdm install
```

## Core Classes

### WittyPi4

Main interface to WittyPi 4 power management hardware.

**Constructor:**

```python
WittyPi4(bus=None, addr=0x08, tz=datetime.UTC)
```

**Parameters:**
- `bus` (SMBus, optional): SMBus instance for I2C communication. If None, creates `SMBus(1, force=True)`
- `addr` (int, optional): I2C address of WittyPi microcontroller (default: 0x08)
- `tz` (tzinfo, optional): Timezone for RTC operations (default: UTC)

**Raises:**
- `WittyPiException`: If device not found or firmware ID doesn't match (expected 0x26)

**Example:**

```python
import smbus2
from wittypi4 import WittyPi4

bus = smbus2.SMBus(1, force=True)
wp = WittyPi4(bus)
```

### ScheduleConfiguration

Manages startup/shutdown scheduling based on time and astronomical events.

**Constructor:**

```python
ScheduleConfiguration(config, tz=None)
```

**Parameters:**
- `config` (dict): Dictionary containing schedule configuration:
  - `lat` (float, optional): Latitude for astronomical calculations
  - `lon` (float, optional): Longitude for astronomical calculations
  - `force_on` (bool, optional): If True, system stays on indefinitely (default: False)
  - `button_delay` (str, optional): Duration string (e.g., "00:30") to stay on after button press
  - `schedule` (list): List of schedule entry dicts with 'name', 'start', 'stop'
- `tz` (tzinfo, optional): Timezone for schedule calculations

**Example:**

```python
from wittypi4 import ScheduleConfiguration

config = {
    'lat': 50.85318,
    'lon': 8.78735,
    'force_on': False,
    'button_delay': '00:30',
    'schedule': [
        {'name': 'morning', 'start': 'sunrise-01:00', 'stop': '12:00'},
        {'name': 'evening', 'start': '18:00', 'stop': 'sunset+01:00'}
    ]
}

sc = ScheduleConfiguration(config)
print(f"Next startup: {sc.next_startup()}")
print(f"Next shutdown: {sc.next_shutdown()}")
print(f"Currently active: {sc.active()}")
```

**Methods:**

- `next_startup(now=None)`: Calculate the next scheduled startup time
- `next_shutdown(now=None)`: Calculate the next scheduled shutdown time
- `active(now=None)`: Check if system should be powered on at given time

### ActionReason

Enumeration of possible reasons for WittyPi 4 power state changes.

**Values:**
- `ALARM_STARTUP (0x01)`: Scheduled startup via Alarm 1
- `ALARM_SHUTDOWN (0x02)`: Scheduled shutdown via Alarm 2
- `BUTTON_CLICK (0x03)`: Manual power button press
- `LOW_VOLTAGE (0x04)`: Shutdown triggered by low input voltage
- `VOLTAGE_RESTORE (0x05)`: Startup after voltage restored above threshold
- `OVER_TEMPERATURE (0x06)`: Shutdown triggered by high temperature
- `BELOW_TEMPERATURE (0x07)`: Shutdown triggered by low temperature
- `ALARM_STARTUP_DELAYED (0x08)`: Startup alarm with configured delay
- `POWER_CONNECTED (0x0A)`: Power source connected
- `REBOOT (0x0B)`: System reboot
- `GUARANTEED_WAKE (0x0C)`: Startup via guaranteed wake feature

**Example:**

```python
from wittypi4 import WittyPi4, ActionReason

wp = WittyPi4()
if wp.action_reason == ActionReason.BUTTON_CLICK:
    print("Powered on by button press")
elif wp.action_reason == ActionReason.ALARM_STARTUP:
    print("Powered on by scheduled alarm")
```

## Hardware Monitoring

### Voltage and Current

Read input/output voltage and current consumption:

```python
wp = WittyPi4()

# Voltage readings (in Volts)
input_voltage = wp.voltage_in
output_voltage = wp.voltage_out

# Current reading (in Amperes)
output_current = wp.current_out

# Power calculation (in Watts)
power = wp.watts_out  # or: voltage_out * current_out
```

### Temperature Monitoring

Read temperature from onboard LM75B sensor:

```python
wp = WittyPi4()
temperature = wp.lm75b_temperature  # in Celsius
```

### Status Summary

Get a comprehensive status dictionary:

```python
wp = WittyPi4()
status = wp.get_status()

# Returns:
# {
#     "Id": 0x26,
#     "Input Voltage (V)": 5.12,
#     "Output Voltage (V)": 5.08,
#     "Output Current (A)": 0.65,
#     "Power Mode": False,
#     "Revision": 0x24,
#     "Temperature (°C)": 32.5
# }
```

## Schedule Management

### YAML Configuration

Create a `schedule.yml` file:

```yaml
# Location coordinates for sunrise/sunset calculations
lat: 50.85318
lon: 8.78735

# Set false to enable schedule, true to stay on indefinitely
force_on: false

# Shutdown delay after manual power-on (HH:MM format, 00:00 disables)
button_delay: "00:30"

# List of schedule entries
schedule:
  - name: morning
    start: sunrise-01:00
    stop: "12:00"
  
  - name: afternoon
    start: "14:00"
    stop: "18:00"
  
  - name: evening
    start: "18:00"
    stop: sunset+01:00
```

### Loading Schedule

```python
import yaml
from wittypi4 import ScheduleConfiguration

with open('schedule.yml', 'r') as f:
    config = yaml.safe_load(f)

sc = ScheduleConfiguration(config)
```

### Schedule Queries

```python
# Check if system should be on right now
if sc.active():
    print("System should be on")

# Get next scheduled startup
next_start = sc.next_startup()
if next_start:
    print(f"Next startup: {next_start}")

# Get next scheduled shutdown
next_stop = sc.next_shutdown()
if next_stop:
    print(f"Next shutdown: {next_stop}")
```

## Alarm Configuration

### Setting Alarms

```python
import datetime
from wittypi4 import WittyPi4

wp = WittyPi4()

# Schedule startup in 1 hour
startup_time = datetime.datetime.now() + datetime.timedelta(hours=1)
wp.set_startup_datetime(startup_time)

# Schedule shutdown in 30 minutes
shutdown_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
wp.set_shutdown_datetime(shutdown_time)

# Disable alarms
wp.set_startup_datetime(None)
wp.set_shutdown_datetime(None)
```

### Reading Alarms

```python
wp = WittyPi4()

# Get currently configured alarms
next_startup = wp.get_startup_datetime()
next_shutdown = wp.get_shutdown_datetime()

print(f"Startup: {next_startup}")
print(f"Shutdown: {next_shutdown}")
```

### Clearing Alarm Flags

After processing an alarm event, clear the flags:

```python
wp = WittyPi4()
wp.clear_flags()  # Clears alarm1_flag, alarm2_flag, and RTC alarm flag
```

## RTC Operations

### Reading RTC Time

```python
wp = WittyPi4()
rtc_time = wp.rtc_datetime
print(f"RTC Time: {rtc_time}")
```

### Setting RTC Time

```python
import datetime
from wittypi4 import WittyPi4

wp = WittyPi4()

# Set RTC to current system time
wp.rtc_datetime = datetime.datetime.now()

# Set RTC to specific time
wp.rtc_datetime = datetime.datetime(2024, 10, 17, 12, 30, 0)
```

### Validating RTC vs System Clock

```python
wp = WittyPi4()

# Check if RTC and system clock match (within 2 seconds by default)
if wp.rtc_sysclock_match():
    print("RTC is synchronized with system clock")
else:
    print("RTC and system clock differ!")
    
# Use custom threshold
if wp.rtc_sysclock_match(threshold=datetime.timedelta(seconds=5)):
    print("RTC matches within 5 seconds")
```

## Configuration Properties

### Power Management

```python
wp = WittyPi4()

# Default power on behavior
wp.default_on = True  # Power on when power connected
wp.default_on_delay = 1  # Delay in seconds before default power-on

# Power cut delay (seconds to wait before cutting power after shutdown signal)
wp.power_cut_delay = 25.0
print(f"Power cut delay: {wp.power_cut_delay}s")
```

### Voltage Thresholds

```python
wp = WittyPi4()

# Low voltage shutdown threshold (in Volts, 0.0 to disable)
wp.lv_threshold = 4.5
print(f"Low voltage threshold: {wp.lv_threshold}V")

# Recovery voltage (voltage to restore power after low voltage shutdown)
wp.recovery_voltage = 4.8
print(f"Recovery voltage: {wp.recovery_voltage}V")
```

### Temperature Actions

```python
wp = WittyPi4()

# Temperature thresholds (in Celsius)
wp.over_temperature_threshold = 60
wp.over_temperature_action = 1  # 0=nothing, 1=shutdown

wp.below_temperature_threshold = -10
wp.below_temperature_action = 1  # 0=nothing, 1=shutdown
```

### LED and Pulse Configuration

```python
wp = WittyPi4()

# LED blink configuration
wp.blink_led = 1  # Enable LED blinking

# Pulse interval for heartbeat signal
wp.pulse_interval = 10  # Interval in 0.1 seconds
```

### Voltage/Current Calibration

Fine-tune voltage and current readings:

```python
wp = WittyPi4()

# Adjustment values (typically -1.00 to +1.00)
wp.adj_vin = 0.05    # Adjust input voltage reading
wp.adj_vout = -0.02  # Adjust output voltage reading
wp.adj_iout = 0.01   # Adjust output current reading
```

### Dumping All Configuration

```python
wp = WittyPi4()

# Get all readable properties as a dictionary
config = wp.dump_config()
for key, value in config.items():
    print(f"{key}: {value}")
```

## Constants Reference

### I2C Address

```python
from wittypi4 import I2C_MC_ADDRESS

# Default I2C address
addr = I2C_MC_ADDRESS  # 0x08
```

### GPIO Pins

```python
from wittypi4 import HALT_PIN, SYSUP_PIN

# GPIO pins (BCM numbering)
halt_pin = HALT_PIN    # 4  - Shutdown signal from WittyPi
sysup_pin = SYSUP_PIN  # 17 - System running signal to WittyPi
```

### I2C Registers

All I2C register addresses are available as constants:

```python
from wittypi4 import (
    I2C_ID,
    I2C_VOLTAGE_IN_I,
    I2C_VOLTAGE_OUT_I,
    I2C_CURRENT_OUT_I,
    I2C_POWER_MODE,
    I2C_ACTION_REASON,
    I2C_FW_REVISION,
    # ... and many more
)
```

## Exception Handling

### WittyPiException

Raised when there are communication errors or unexpected hardware responses:

```python
from wittypi4 import WittyPi4, WittyPiException
import smbus2

try:
    bus = smbus2.SMBus(1, force=True)
    wp = WittyPi4(bus)
    print("Connected successfully")
except WittyPiException as e:
    print(f"Failed to connect to WittyPi: {e}")
except OSError as e:
    print(f"I2C communication error: {e}")
```

### Common Error Scenarios

**Device not found:**
```python
# Error: "error reading address 0x08, check device connection"
# Solution: Check I2C wiring and enable I2C in raspi-config
```

**Wrong firmware version:**
```python
# Error: "unknown Firmware Id (got 0xXX, expected 0x26)"
# Solution: Update WittyPi firmware or verify correct device
```

**RTC validation failed (daemon mode):**
```python
# Exit code 3: RTC time is implausible or not synchronized
# Solution: Wait for NTP sync or manually set system time
```

## Advanced Usage

### Using with Context Manager

```python
import smbus2
from wittypi4 import WittyPi4

class WittyPiContext(WittyPi4):
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._bus.close()

with WittyPiContext() as wp:
    print(wp.voltage_in)
    wp.set_startup_datetime(...)
```

### Monitoring Power Consumption

```python
import time
from wittypi4 import WittyPi4

wp = WittyPi4()

print("Monitoring power consumption (Ctrl+C to stop):")
try:
    while True:
        print(f"Vin: {wp.voltage_in:.2f}V, "
              f"Vout: {wp.voltage_out:.2f}V, "
              f"Iout: {wp.current_out:.2f}A, "
              f"Power: {wp.watts_out:.2f}W")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopped")
```

### Schedule with Multiple Time Zones

```python
import datetime
from wittypi4 import WittyPi4

# Use specific timezone for RTC operations
berlin_tz = datetime.timezone(datetime.timedelta(hours=1))
wp = WittyPi4(tz=berlin_tz)

# All RTC operations now use Berlin timezone
print(wp.rtc_datetime)
```

## See Also

- [Main README](../Readme.md) - Hardware setup and installation
- [Example Schedule](../schedule.yml) - Example schedule configuration
- [WittyPi 4 User Manual](https://www.uugear.com/doc/WittyPi4_UserManual.pdf) - Official hardware documentation

