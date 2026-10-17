#!/usr/bin/env bash
# Builds our own Pd objects (dcs/) for Android into app/src/main/jniLibs/<abi>/libdcs.so (committed, like pd-core,
# so ordinary app builds need no NDK). Run it after changing dcs/src. Needs the NDK 29.0.14206865 and the pd-core
# aar in third_party/maven (its libpd.so is what libdcs.so links against) and Pd's headers (tools/build_libpd.sh).
set -e
H="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$H")"
NDK="${ANDROID_NDK_HOME:-$HOME/Android/Sdk/ndk/29.0.14206865}"
AAR="$ROOT/third_party/maven/io/github/libpd/android/pd-core/1.4.2-pdscenes.1/pd-core-1.4.2-pdscenes.1.aar"
PD_SRC="$H/.libpd/src/pure-data/src"
[ -f "$PD_SRC/m_pd.h" ] || { echo "Pd's headers are missing: run tools/build_libpd.sh first"; exit 1; }
W="$H/.dcs-android"; rm -rf "$W"; mkdir -p "$W/aar"
unzip -q "$AAR" 'jni/*' -d "$W/aar"
"$NDK/ndk-build" -s -C "$ROOT/dcs/android" NDK_PROJECT_PATH=. APP_BUILD_SCRIPT=Android.mk \
    NDK_APPLICATION_MK=Application.mk NDK_OUT="$W/obj" NDK_LIBS_OUT="$W/libs" \
    PDCORE_JNI="$W/aar/jni" PD_SRC="$PD_SRC"
for abi in armeabi-v7a arm64-v8a x86 x86_64; do
    mkdir -p "$ROOT/app/src/main/jniLibs/$abi"
    cp "$W/libs/$abi/libdcs.so" "$ROOT/app/src/main/jniLibs/$abi/"     # (not libpd.so: pd-core brings it)
done
echo "libdcs.so built:"; ls -la "$ROOT"/app/src/main/jniLibs/*/libdcs.so
