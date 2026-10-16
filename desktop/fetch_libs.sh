#!/usr/bin/env bash
# Gets what the desktop version needs into desktop/lib (not in git): libpd's Java connection, built from the same
# libpd the tests and the phone use (our fork in tools/.libpd, see tools/build_libpd.sh), and four jars from Maven Central, checked by SHA-1.
set -e
H="$(cd "$(dirname "$0")" && pwd)"; L="$H/lib"; mkdir -p "$L"
SRC="$H/../tools/.libpd/src"
[ -d "$SRC" ] || { echo "Build desktop libpd first: tools/build_libpd.sh"; exit 1; }
[ -x "$JAVA_HOME/bin/javac" ] || JAVA_HOME="$HOME/.jdks/jbr-21.0.11"; export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
make -C "$SRC" javalib -j8 >/dev/null
cp "$SRC/libs/libpd.jar" "$SRC/libs/libpdnative.so" "$L/"
cp "$SRC/.pdscenes-commit" "$L/libpd-commit"   # run.sh rebuilds when tools/build_libpd.sh moves the pin
get() {   # path on Maven Central, sha1
  local f="$L/$(basename "$1")"
  [ -f "$f" ] || curl -sSfL -o "$f" "https://repo1.maven.org/maven2/$1"
  echo "$2  $f" | sha1sum -c --quiet || { rm -f "$f"; echo "Checksum failed: $1"; exit 1; }
}
get org/jaudiolibs/jnajack/1.4.0/jnajack-1.4.0.jar b7a21342efe2e50cb752b6255be8861f954319dc
get net/java/dev/jna/jna/5.14.0/jna-5.14.0.jar 67bf3eaea4f0718cb376a181a629e5f88fa1c9dd
get org/json/json/20240303/json-20240303.jar 0ebb88e8fb5122b7506d5cf1d69f1ccdb790d22a
get com/formdev/flatlaf/3.4.1/flatlaf-3.4.1.jar 59161ce93728eaec725a26d646f7eff1d363decd
echo "desktop/lib ready"
