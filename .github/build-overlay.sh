#!/bin/bash
# Build the wittypi4 overlay and check it applies to the Raspberry Pi device trees.
# Runs as root in a debian:trixie container (CI, or locally via docker).
#
# Usage: build-overlay.sh <outdir>
# Output: <outdir>/boot/firmware/overlays/wittypi4.dtbo
set -euo pipefail

OUT=$(realpath -m "$1")
SRC=$(realpath "$(dirname "$0")/../wittypi4-overlay.dts")
DTBO="$OUT/boot/firmware/overlays/wittypi4.dtbo"
# Boards the overlay is enabled on (tsOS: [pi3] and [pi4]).
BOARDS=(bcm2710-rpi-3-b bcm2710-rpi-3-b-plus bcm2711-rpi-4-b)
FIRMWARE=https://raw.githubusercontent.com/raspberrypi/firmware/master/boot

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl device-tree-compiler

# dtc only warns about e.g. bad references; treat that as an error.
mkdir -p "$(dirname "$DTBO")"
dtc -O dtb -o "$DTBO" "$SRC" 2> /tmp/dtc.log
if [ -s /tmp/dtc.log ]; then
    cat /tmp/dtc.log >&2
    exit 1
fi

# Apply to each board's base tree, like the firmware does at boot.
for board in "${BOARDS[@]}"; do
    curl -fsSL -o "/tmp/$board.dtb" "$FIRMWARE/$board.dtb"
    fdtoverlay -i "/tmp/$board.dtb" -o /tmp/merged.dtb "$DTBO"

    i2c=$(fdtget /tmp/merged.dtb /__symbols__ i2c_arm)
    children=$(fdtget -l /tmp/merged.dtb "$i2c/rtc@8" | sort | tr '\n' ' ')
    if [ "$children" != "leds shutdown " ]; then
        echo "$board: unexpected children of $i2c/rtc@8: $children" >&2
        exit 1
    fi
    if [ "$(fdtget /tmp/merged.dtb "$i2c" status)" != okay ]; then
        echo "$board: $i2c is not enabled" >&2
        exit 1
    fi
    echo "Applied overlay to $board"
done
