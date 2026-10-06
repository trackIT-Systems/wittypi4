# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
from `0.1.0` on. The earlier tags `rpi-6.1.y`, `rpi-6.6.y` and `rpi-6.12.y` name the
Raspberry Pi kernel series they were built for and predate versioning.

## [Unreleased]

## [0.2.0] - 2026-10-06

### Changed

- **Breaking:** the RTC driver no longer contains its own copy of `rtc-pcf85063`. It is a nested I2C adapter that maps the RTC registers behind the MCU and binds the in-tree `rtc-pcf85063` driver, which must be enabled (`CONFIG_RTC_DRV_PCF85063`)
- **Breaking:** `dtoverlay=wittypi4` now also sets up the shutdown key (GPIO4) and the SYSUP LED (GPIO17), and enables the ARM I2C bus. Remove the `dtoverlay=gpio-shutdown,gpio_pin=4,...` and `dtoverlay=gpio-led,gpio=17,...` lines from `config.txt`, as they would claim the same pins ([#2])
- **Breaking:** requires `scheduleparse` 2026.10.1
- The driver checks for the Witty Pi 4 firmware id (`0x26`) before binding, and only then creates the shutdown key and SYSUP LED. The overlay can therefore be enabled on systems without the board
- The overlay adds the compatible `uugear,wittypi4-rtc-proxy`; `nxp,pcf85063wp` still binds
- The DKMS package version is `1.0` and no longer tied to a kernel series
- Schedules default to the system timezone with its DST rules instead of a fixed UTC offset, which was off by an hour after a DST change
- On termination, `wittypid` computes the next startup from the RTC, like its main loop

### Fixed

- Schedule windows between local midnight and UTC midnight (e.g. 00:01-01:00 in Europe/Berlin) were evaluated on the wrong day and never woke the system ([#9])
- An unknown action reason from newer firmware crashed `wittypid` at startup; it now maps to `REASON_NA`
- A sunrise/sunset schedule entry without a location (lat/lon or `/etc/geolocation`) crashed `wittypid` at startup; it is now skipped with a warning
- `ButtonEntry` computes the boot time once instead of on every call, so `next_shutdown()` always converges
- Voltage and current adjustments (`adj_vin`, `adj_vout`, `adj_iout`) were truncated instead of rounded, so some values were written 0.01 off (e.g. -1.16 V as -1.15 V)
- Built wheels contained only metadata, no code
- The Readme described the shutdown key as active high; the MCU pulls GPIO4 low

### Added

- Releases are built in CI and contain:
  - a tarball with the kernel modules for every Raspberry Pi 6.18 kernel (`rpi-v8`, `rpi-2712`, `rpi-v8-rt`) and the overlay as `boot/firmware/overlays/wittypi4.dtbo`, checked against the Raspberry Pi 3 and 4 device trees
  - the Python sdist and wheel, versioned from the tag
  - release notes from this changelog
- Tests for the hardware class, schedule edge cases and the daemon, including a two-day simulation of `wittypid` and the firmware's alarm handling
- CI runs the tests on Python 3.11 to 3.14 for every push; releases require them to pass

## [0.1.0] - 2025-12-11

### Added

- Action reason `REASON_NA` for "no reason" ([#10])
- Location for sunrise/sunset schedules from `/etc/geolocation` (geoclue format) when the schedule has no lat/lon
- The RTC plausibility check also accepts the last systemd-timesyncd and chrony synchronization, besides fake-hwclock ([#8])
- API documentation (`docs/API.md`) and docstrings

### Changed

- A startup because power was connected keeps the system on for `button_delay`, like a button click
- `wittypid` creates `/run/systemd/timesync/` instead of waiting for it

### Fixed

- The driver no longer sends a software reset on load, which reset the RTC time; it retries detecting the RTC up to 3 times instead

## [rpi-6.12.y] - 2025-10-08

### Added

- Support for newer Witty Pi 4 firmware: action reasons `POWER_CONNECTED`, `REBOOT` and `GUARANTEED_WAKE`, and the `MISC` and `GUARANTEED_WAKE` registers ([#1])
- Unknown action reasons are logged instead of raising ([#1])
- `wittypid` logs the firmware revision on startup
- `etc/wittypid-power.service` sets GPIO14 (TxD) low on shutdown, so the Witty Pi reliably cuts power
- License (GPL-3.0)

### Changed

- Schedule entries are parsed by the `scheduleparse` package
- `wittypid` sets the power cut delay explicitly, now 25 s ([#4])
- Schedules and the RTC use the system timezone instead of UTC ([#5])
- Build for kernel 6.12

### Fixed

- `ButtonEntry` could make the schedule evaluation loop forever
- Wrong stop times of schedule entries, and of `ButtonEntry`, in the shutdown calculation
- `/etc/fake-hwclock.data` was parsed incorrectly
- The power cut delay is clamped to the register's range
- The driver sends a software reset on load, so a rebooted Raspberry Pi detects the RTC

## [rpi-6.6.y] - 2024-07-08

### Changed

- Build for kernel 6.6
- Python dependencies are minimum versions instead of compatible releases

## [rpi-6.1.y] - 2024-04-15

### Added

- RTC kernel driver `rtc-pcf85063-wittypi4` and device tree overlay for the PCF85063 behind the Witty Pi 4 MCU
- Python library `wittypi4`: voltages, current, temperature, configuration registers, alarms, RTC and `get_status()`
- Daemon `wittypid`: sets startup and shutdown alarms from a YAML schedule with absolute and sunrise/sunset-relative times, overlapping entries, and a `button_delay` after manual power-on (can be disabled)
- `wittypid` shuts down immediately after a shutdown alarm, and handles a missing Witty Pi gracefully
- `powerbench.py` and debug scripts

[Unreleased]: https://github.com/trackIT-Systems/wittypi4/compare/0.2.0...HEAD
[0.2.0]: https://github.com/trackIT-Systems/wittypi4/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/trackIT-Systems/wittypi4/compare/rpi-6.12.y...0.1.0
[rpi-6.12.y]: https://github.com/trackIT-Systems/wittypi4/compare/rpi-6.6.y...rpi-6.12.y
[rpi-6.6.y]: https://github.com/trackIT-Systems/wittypi4/compare/rpi-6.1.y...rpi-6.6.y
[rpi-6.1.y]: https://github.com/trackIT-Systems/wittypi4/tree/rpi-6.1.y
[#1]: https://github.com/trackIT-Systems/wittypi4/pull/1
[#2]: https://github.com/trackIT-Systems/wittypi4/issues/2
[#4]: https://github.com/trackIT-Systems/wittypi4/issues/4
[#5]: https://github.com/trackIT-Systems/wittypi4/issues/5
[#8]: https://github.com/trackIT-Systems/wittypi4/issues/8
[#9]: https://github.com/trackIT-Systems/wittypi4/issues/9
[#10]: https://github.com/trackIT-Systems/wittypi4/issues/10
