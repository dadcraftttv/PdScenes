#!/usr/bin/env bash
# Builds desktop libpd into tools/.libpd/libpd.so (the Python Pd tests) and leaves its source in tools/.libpd/src
# (desktop/fetch_libs.sh builds the desktop app's Java libpd from it).
# Same libpd as the app's pd-core (see tools/build_pdcore.sh): our fork dadcraftttv/libpd, branch pdscenes, pinned by
# commit = libpd 3fc60ea (Pd 0.55.2) + #428 (an Android Oboe fix, not compiled here), so the tests and the desktop
# hear what the phone hears. Newer Pd (0.56) breaks StreetBeatz.rj. Change this pin together with the pd-core one.
set -e
COMMIT=ebc0b8372b540053398a83c2ab2e8e5dbcf1313a
REPO=https://github.com/dadcraftttv/libpd.git
D="$(cd "$(dirname "$0")" && pwd)/.libpd"
mkdir -p "$D"; cd "$D"
if [ -d src ] && [ "$(cat src/.pdscenes-commit 2>/dev/null)" != "$COMMIT" ]; then rm -rf src; fi
if [ ! -d src ]; then
    git clone -q "$REPO" src
    git -C src checkout -q "$COMMIT"
    git -C src submodule update -q --init --recursive
    echo "$COMMIT" > src/.pdscenes-commit
fi
cd src && make -j"$(nproc)"
cp libs/libpd.so "$D/libpd.so"
echo "Built $D/libpd.so (libpd $REPO $COMMIT)"
