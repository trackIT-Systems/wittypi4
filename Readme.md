WittyPi 4
---

This repository holds implementations for alternative WittyPi 4 usage with modern linux distributions.

# Basic usage

The basic workflow followed by the WittyPi is described in the figure cited from UUGear's manual:

![WittyPi basic workflow, as seen in UUGear's user manual, Chapter 4.](img/wittypi_workflow.jpg)

To enable turning the Raspberry Pi on and shutting it down gracefully, one can make use of existing dtoverlays, described in `/boot/firmware/overlays/README`:

```
Name:   gpio-shutdown
Info:   Initiates a shutdown when GPIO pin changes. The given GPIO pin
        is configured as an input key that generates KEY_POWER events.
...
Name:   gpio-led
Info:   This is a generic overlay for activating LEDs (or any other component)
        by a GPIO pin.
```

WittyPi uses inverted logic for the shutdown button, i.e. `active_high`. Also the virtual button press is quite short (can be < 1ms), hence debouncing shoud be disabled. Using the following entries in `/boot/firmware/config.txt`, sysup and shutdown is made available:

```ini
dtoverlay=gpio-shutdown,gpio_pin=4,debounce=0,active_low=0
dtoverlay=gpio-led,gpio=17,label=sysup,trigger=heartbeat
```

> Note: The SYSUP signal `(0, 1, 0, 1)` in 100ms intervals is sent using the trigger `heartbeat`, as this by accident matches the required interval. 

## Real Time Clock (RTC) Linux Driver

In order to use the real time clock in linux, a kernel module shall be loaded. While there exists an implementation of PCF85063A in the mainline kernel, it doesn't allow to be loaded with shifted register adresses. The linux `regmap` hardware abstraction allows however allows this modifications in a convenient fashion using the [`reg_base`](https://elixir.bootlin.com/linux/latest/source/include/linux/regmap.h#L260) property; *Value to be added to every register address before performing any operation.*

The linux driver for PCF85063A was forked and adapted to the WittyPi 4 shifted registers. Debugging the driver it became obvious, that the WittyPi interface doesn't support bulk reads and writes, an i2c feature, only returning `0xff` for the respective reads.. Again `regmap` allows to disable these type of reads. 

In addition to this alarms should be disabled, as they are used by the WittyPi itself.

The device configuration for an adapted driver looks like this:

```c
	[PCF85063A_WITTYPI] = {
		.regmap = {
			.reg_bits = 8,
			.val_bits = 8,
			.max_register = 0x11,
			.reg_base = 0x36,
			.use_single_read = true,
			.use_single_write = true,
		},
		.has_alarms = 0,
	},
```

### Compile & Install module

The module can either be compiled using the Makefile, i.e. `make; sudo make install` or via dkms:

```bash
# copy source files
sudo cp -R /home/pi/wittypi4 /usr/src/wittypi4-6.6.y
# install & compile using dkms
sudo dkms install wittypi4/6.6.y
```

### Device Tree Overlay / Raspberry Pi

To load the driver and make the RTC accessible to the Raspberry Pi a device tree overlay can be used ([wittypi4-overlay.dts](./wittypi4-overlay.dts)). To use this overlay it needs to be compiled and loaded:

```bash
# compile to dtbo 
dtc -O dtb -o wittypi4.dtbo wittypi4-overlay.dts
# create overlay location
sudo mkdir -p /sys/kernel/config/device-tree/overlays/wittypi4
# copy dtbo to kernel interface
sudo cp wittypi4.dtbo /sys/kernel/config/device-tree/overlays/wittypi4/dtbo
```

Of course the dtbo can also be loaded using an `config.txt` entry inside, when copying the dtbo to the respective location:

```bash
# copy dtbo to overlay folder
sudo cp wittypi4.dtbo /boot/firmware/overlays/
# append dtoverlay to config.txt
sudo tee -a /boot/firmware/config.txt <<<dtoverlay=wittypi4
```

### TxD power cut

WittyPi recogices a the Raspberry Pi's shutdown by monitoring the TxD output. This mostly works reliable, but sometimes leads to a hangup where the Raspberry Pi shutdown, but TxD is still high and power is not cut. 

To make this more reliable a systemd service can be created, that forcefully sets GPIO 14 low (and thereby disables TxD / the serial console). An example service is to be found in `[/etc/wittypid-power.service](/etc/wittypid-power.service)`.

## Resources

### Datasheets
- [WittyPi 4](https://www.uugear.com/doc/WittyPi4_UserManual.pdf)
- [PCF85063A](https://www.nxp.com/docs/en/data-sheet/PCF85063A.pdf) (RTC)
- [LM75B](https://www.ti.com/lit/ds/symlink/lm75b.pdf)
