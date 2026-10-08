#!/usr/bin/env bash
# Builds desktop libpd (used only by the Python Pd tests) into tools/.libpd/libpd.so
# Pinned to the libpd release with the same Pd version as the app's pd-core (Pd 0.55.2), so the tests hear
# what the phone hears. Newer Pd (0.56) breaks StreetBeatz.rj. Change both together.
set -e
TAG=0.15.0
D="$(cd "$(dirname "$0")" && pwd)/.libpd"
mkdir -p "$D"; cd "$D"
if [ -d src ] && [ "$(cat src/.pdscenes-tag 2>/dev/null)" != "$TAG" ]; then rm -rf src; fi
[ -d src ] || { git clone --recurse-submodules --depth 1 --branch "$TAG" https://github.com/libpd/libpd src \
                && echo "$TAG" > src/.pdscenes-tag; }
cd src && make -j"$(nproc)"
cp libs/libpd.so "$D/libpd.so"
echo "Built $D/libpd.so (libpd $TAG)"
