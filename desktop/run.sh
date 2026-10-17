#!/usr/bin/env bash
# Builds and runs the desktop version. It talks to PipeWire through its JACK layer, so it starts under pw-jack.
# Arguments go to the program (see DesktopApp.java): --no-window, --seconds N.
set -e
H="$(cd "$(dirname "$0")" && pwd)"
[ -x "$JAVA_HOME/bin/javac" ] || JAVA_HOME="$HOME/.jdks/jbr-21.0.11"; export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"; unset JAVA_TOOL_OPTIONS
[ -f "$H/lib/libpdnative.so" ] && [ -f "$H/lib/flatlaf-3.4.1.jar" ] \
    && cmp -s "$H/lib/libpd-commit" "$H/../tools/.libpd/src/.pdscenes-commit" || "$H/fetch_libs.sh"
CP="$H/lib/libpd.jar:$H/lib/jnajack-1.4.0.jar:$H/lib/jna-5.14.0.jar:$H/lib/json-20240303.jar:$H/lib/flatlaf-3.4.1.jar"
A="$H/../app/src/main/java/app/pdscenes"
# the phone app's own logic, unchanged, with desktop stand-ins (shim/) for the little Android it touches
SHARED="Param Params ParamStore PresetManager Modulation PhoneContext Intensity CalmBuild PackPlayer StemPack Worlds WorldSelector MotifMemory NoteRegister CallResponse Kits"
make -s -C "$H/../dcs"   # our own Pd objects (build/dcs.pd_linux), loaded by the patch
rm -rf "$H/build"; mkdir -p "$H/build"
javac -d "$H/build" -cp "$CP" $(for c in $SHARED; do echo "$A/$c.java"; done) $(find "$H/shim" "$H/src" -name '*.java')
# (Pd 0.55.2's expr prints a leftover debug line, "realloc called with N bytes", whenever it grows a buffer)
# 256 samples a cycle (~6 ms): Pd holds its lock while it works on a cycle, and at 1024 the window's slider moves
# and readings waited on it (and the voice was ~23 ms late). PDSCENES_PERIOD changes it.
# (asked at the graph's own rate: pw-jack -p would also force 48 kHz)
RATE=$(pw-metadata -n settings 0 clock.rate 2>/dev/null | grep -o "value:'[0-9]*" | cut -d"'" -f2)
PIPEWIRE_LATENCY="${PDSCENES_PERIOD:-256}/${RATE:-48000}" pw-jack java -Djava.library.path="$H/lib" -Dpdscenes.dcs="$H/../dcs/build" -Dawt.useSystemAAFontSettings=on -cp "$H/build:$CP" app.pdscenes.DesktopApp \
    --patch "$H/../app/src/main/assets/patches/test_scene.pd" "$@" 2>&1 | grep --line-buffered -v "^realloc called with"
