#!/usr/bin/env bash
# Builds and runs the desktop version. It talks to PipeWire through its JACK layer, so it starts under pw-jack.
# Arguments go to the program (see Engine.java), e.g. desktop/run.sh --game --set beat_level=0.5
set -e
H="$(cd "$(dirname "$0")" && pwd)"
[ -x "$JAVA_HOME/bin/javac" ] || JAVA_HOME="$HOME/.jdks/jbr-21.0.11"; export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"; unset JAVA_TOOL_OPTIONS
[ -f "$H/lib/libpdnative.so" ] || "$H/fetch_libs.sh"
CP="$H/lib/libpd.jar:$H/lib/jnajack-1.4.0.jar:$H/lib/jna-5.14.0.jar:$H/lib/json-20240303.jar"
rm -rf "$H/build"; mkdir -p "$H/build"
javac -d "$H/build" -cp "$CP" $(find "$H/src" -name '*.java')
# (Pd 0.55.2's expr prints a leftover debug line, "realloc called with N bytes", whenever it grows a buffer)
pw-jack java -Djava.library.path="$H/lib" -cp "$H/build:$CP" app.pdscenes.desktop.Engine \
    --patch "$H/../app/src/main/assets/patches/test_scene.pd" "$@" 2>&1 | grep --line-buffered -v "^realloc called with"
