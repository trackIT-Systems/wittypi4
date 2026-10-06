WittyPi 4
---

This repository holds implementations for alternative WittyPi 4 usage with modern linux distributions.

# Basic usage

The basic workflow followed by the WittyPi is described in the figure cited from UUGear's manual:

![WittyPi basic workflow, as seen in UUGear's user manual, Chapter 4.](img/wittypi_workflow.jpg)

The overlay [wittypi4-overlay.dts](./wittypi4-overlay.dts) integrates the WittyPi with the system in one `dtoverlay=wittypi4` (see [Device Tree Overlay](#device-tree-overlay--raspberry-pi)):

- **Shutdown**: the MCU pulls GPIO4 low on a button click or shutdown alarm. GPIO4 is an input with pull-up and generates `KEY_POWER` (like the stock `gpio-shutdown` overlay). Debouncing is disabled, as the pulse can be < 1ms.
- **SYSUP**: GPIO17 signals the MCU that the system is up, as LED `sysup` (like the stock `gpio-led` overlay).
- **RTC**: the PCF85063 behind the MCU, see below. The overlay also enables the ARM I2C bus.

Shutdown and SYSUP are only set up once the driver `rtc-pcf85063-wittypi4` found the WittyPi (firmware id `0x26` at `0x08`). The overlay can therefore be enabled on systems without the board; GPIO4 and GPIO17 then stay untouched.

It replaces the previous combination of three overlays:

```ini
dtoverlay=wittypi4
dtoverlay=gpio-shutdown,gpio_pin=4,debounce=0,gpio_pull=up,active_low=1
dtoverlay=gpio-led,gpio=17,label=sysup,trigger=heartbeat
```

> Note: The SYSUP signal `(0, 1, 0, 1)` in 100ms intervals is sent using the trigger `heartbeat`, as this by accident matches the required interval. 

## Real Time Clock (RTC) Linux Driver

Witty Pi 4 exposes the PCF85063 through the MCU at I2C address `0x08`, with RTC registers windowed at offset `0x36`. The MCU also rejects bulk I2C transfers (bulk reads come back as `0xff`).

This repository does **not** fork `rtc-pcf85063`. Module `rtc-pcf85063-wittypi4` is a nested I2C adapter that:

- adds `0x36` to the register byte and forwards to the MCU at `0x08`
- splits bulk / combined transfers into single-byte accesses
- retries NAK / MCU-not-ready a few times on first access
- instantiates a child client (`pcf85063a` at virtual address `0x51`) for the **in-tree** `rtc-pcf85063` driver

`CONFIG_RTC_DRV_PCF85063` (module `rtc-pcf85063`) must be enabled. The overlay does not wire an RTC IRQ, so kernel alarms stay off (the MCU uses the alarm itself).

The overlay compatible list is `"uugear,wittypi4-rtc-proxy", "nxp,pcf85063wp"` so existing `nxp,pcf85063wp` nodes still bind.
### Compile & Install module

The module can either be compiled using the Makefile, i.e. `make; sudo make install` or via dkms:

```bash
# copy driver source files
sudo cp -R /home/pi/wittypi4/rtc-pcf85063-wittypi4 /usr/src/rtc-pcf85063-wittypi4-1.0
# install & compile using dkms
sudo dkms install rtc-pcf85063-wittypi4/1.0
```

### Device Tree Overlay / Raspberry Pi

The overlay ([wittypi4-overlay.dts](./wittypi4-overlay.dts)) loads the RTC driver and sets up shutdown and SYSUP. Compile it, copy it to the overlay folder and enable it in `config.txt`:

```bash
# compile to dtbo
dtc -O dtb -o wittypi4.dtbo wittypi4-overlay.dts
# copy dtbo to overlay folder
sudo cp wittypi4.dtbo /boot/firmware/overlays/
# append dtoverlay to config.txt
sudo tee -a /boot/firmware/config.txt <<<dtoverlay=wittypi4
```

Releases ship a prebuilt `boot/firmware/overlays/wittypi4.dtbo` in `rtc-pcf85063-wittypi4-modules.tar.gz`, next to the matching modules.

Remove any `dtoverlay=gpio-shutdown,gpio_pin=4,...` and `dtoverlay=gpio-led,gpio=17,...` lines, as they would claim the same pins.

### TxD power cut

WittyPi recogices a the Raspberry Pi's shutdown by monitoring the TxD output. This mostly works reliable, but sometimes leads to a hangup where the Raspberry Pi shutdown, but TxD is still high and power is not cut. 

To make this more reliable a systemd service can be created, that forcefully sets GPIO 14 low (and thereby disables TxD / the serial console). An example service is to be found in `[/etc/wittypid-power.service](/etc/wittypid-power.service)`.

# Python API

This repository includes a Python library for programmatic control of the WittyPi 4.

## Installation

Install the library using pip or pdm:

```bash
# Using pip
pip install -e .

# Using pdm
pdm install
```

## Quick Example

```python
import smbus2
from wittypi4 import WittyPi4
import datetime

# Initialize WittyPi 4
bus = smbus2.SMBus(1, force=True)
wp = WittyPi4(bus)

# Read hardware status
print(f"Input: {wp.voltage_in}V, Output: {wp.voltage_out}V @ {wp.current_out}A")
print(f"Temperature: {wp.lm75b_temperature}°C")
print(f"RTC Time: {wp.rtc_datetime}")

# Schedule next startup in 1 hour
wp.set_startup_datetime(datetime.datetime.now() + datetime.timedelta(hours=1))
```

## Running the Daemon

The `wittypid` daemon manages schedules automatically:

```bash
# Run with default schedule.yml
wittypid

# Run with custom schedule file
wittypid -s /path/to/schedule.yml

# Verbose output
wittypid -vv
```

For production use, install as a systemd service (see `etc/wittypid-power.service`).

## Documentation

For complete API reference, examples, and advanced usage, see:
- [Python API Documentation](docs/API.md) - Complete API reference for developers
- [schedule.yml](schedule.yml) - Example schedule configuration

## Resources

### Datasheets
- [WittyPi 4](https://www.uugear.com/doc/WittyPi4_UserManual.pdf)
- [PCF85063A](https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf) (RTC)
- [LM75B](https://www.ti.com/lit/ds/symlink/lm75b.pdf)
