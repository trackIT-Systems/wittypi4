MOD_NAME	:= rtc-pcf85063-wittypi4

ifneq ($(KERNELRELEASE),)

# call from kernel build system

all:
	@echo "Building from the kernel build system"
	@echo "Module build: $(RTC_DRV_PCF85063_WITTYPI4)"
	@echo "Name: $(MOD_NAME)"

obj-$(RTC_DRV_PCF85063_WITTYPI4) := $(MOD_NAME).o

else
# external module build

EXTRA_FLAGS += -I$(PWD)

#
# KDIR is a path to a directory containing kernel source.
# It can be specified on the command line passed to make to enable the module to
# be built and installed for a kernel other than the one currently running.
# By default it is the path to the symbolic link created when
# the current kernel's modules were installed, but
# any valid path to the directory in which the target kernel's source is located
# can be provided on the command line.
#
KDIR	?= /lib/modules/$(shell uname -r)/build
MDIR	?= /lib/modules/$(shell uname -r)
PWD	:= $(shell pwd)
PWD	:= $(shell pwd)

export RTC_DRV_PCF85063_WITTYPI4 := m

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

help:
	$(MAKE) -C $(KDIR) M=$(PWD) help

install: $(MOD_NAME).ko
	rm -f ${MDIR}/kernel/drivers/rtc/$(MOD_NAME).ko
	install -m644 -b -D $(MOD_NAME).ko ${MDIR}/kernel/drivers/rtc/$(MOD_NAME).ko
	depmod -a

uninstall:
	rm -rf ${MDIR}/kernel/drivers/rtc/$(MOD_NAME).ko
	depmod -a
endif

wittypi4.dtbo: wittypi4-overlay.dts
	dtc -O dtb -o $@ $<

.PHONY : all clean install uninstall

