#!/usr/bin/env bash
# Builds desktop libpd (used only by the Python Pd tests) into tools/.libpd/libpd.so
set -e
D="$(cd "$(dirname "$0")" && pwd)/.libpd"
mkdir -p "$D"; cd "$D"
[ -d src ] || git clone --recurse-submodules --depth 1 https://github.com/libpd/libpd src
cd src && make -j"$(nproc)"
cp libs/libpd.so "$D/libpd.so"
echo "Built $D/libpd.so"
