#!/bin/bash
# Build rtc-pcf85063-wittypi4 for every Raspberry Pi kernel of one flavor and series.
# Runs as root in a debian:trixie arm64 container (CI, or locally via docker).
#
# Usage: build-modules.sh <flavor> <series> <outdir>
#   e.g. build-modules.sh rpi-v8 6.18 out
# Output: <outdir>/lib/modules/<kver>/updates/rtc-pcf85063-wittypi4.ko
set -euo pipefail

FLAVOR=$1
SERIES=$2
OUT=$(realpath -m "$3")
SRC=$(realpath "$(dirname "$0")/../rtc-pcf85063-wittypi4")
MOD=rtc-pcf85063-wittypi4

export DEBIAN_FRONTEND=noninteractive

# Raspberry Pi apt repository - the index keeps old kernel versions, so
# headers for kernels in already-released images stay installable.
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl make kmod
# The repo's legacy raspberrypi.gpg.key has a SHA-1 binding that trixie's sqv
# rejects; the keyring package ships a current key. Pinned by hash, as it is the
# trust anchor for everything installed from that repository.
KEYRING_DEB=raspberrypi-archive-keyring_2025.1+rpt1_all.deb
KEYRING_SHA256=2e727149d7acb8cc7f604e66d0049161039c8aa1eaf1175e54f9e69d963d60e4
curl -fsSL -o "/tmp/$KEYRING_DEB" \
    "https://archive.raspberrypi.com/debian/pool/main/r/raspberrypi-archive-keyring/$KEYRING_DEB"
echo "$KEYRING_SHA256  /tmp/$KEYRING_DEB" | sha256sum -c -
dpkg -i "/tmp/$KEYRING_DEB"
cat > /etc/apt/sources.list.d/raspi.sources <<SOURCES
Types: deb
URIs: https://archive.raspberrypi.com/debian/
Suites: trixie
Components: main
Signed-By: /usr/share/keyrings/raspberrypi-archive-keyring.pgp
SOURCES
apt-get update

mapfile -t PKGS < <(apt-cache pkgnames linux-headers- \
    | grep -E "^linux-headers-${SERIES//./\\.}\.[0-9]+\+rpt-${FLAVOR}\$" | sort -V)
if [ ${#PKGS[@]} -eq 0 ]; then
    echo "No linux-headers-${SERIES}.*+rpt-${FLAVOR} packages found" >&2
    exit 1
fi
# The headers pull in gcc-14-for-host and linux-kbuild, i.e. the kernel's own compiler.
apt-get install -y --no-install-recommends binutils "${PKGS[@]}"

for pkg in "${PKGS[@]}"; do
    kver=${pkg#linux-headers-}
    build=$(mktemp -d)
    cp -R "$SRC"/. "$build"
    make -C "$build" KDIR="/usr/src/linux-headers-$kver"

    vermagic=$(modinfo -F vermagic "$build/$MOD.ko")
    if [ "${vermagic%% *}" != "$kver" ]; then
        echo "vermagic mismatch for $kver: $vermagic" >&2
        exit 1
    fi

    install -m644 -D "$build/$MOD.ko" "$OUT/lib/modules/$kver/updates/$MOD.ko"
    rm -rf "$build"
    echo "Built $MOD for $kver"
done
