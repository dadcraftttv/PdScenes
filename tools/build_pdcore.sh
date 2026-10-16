#!/usr/bin/env bash
# Builds the app's pd-core (Pure Data for Android) from our forks and puts it in third_party/maven, where the app's
# Gradle build finds it. Run it only to change what the app is built with: the result is committed, so ordinary
# builds need no NDK.
#
#   dadcraftttv/pd-for-android, branch pdscenes = libpd/pd-for-android master (d3ec6c9) + #198 (setAutoReopen)
#   dadcraftttv/libpd,          branch pdscenes = libpd 3fc60ea (Pd 0.55.2, what pd-core 1.4.2-SNAPSHOT used)
#                                                 + #428 (the Oboe reopen/close race fix, our issue #427)
#
# Pinned by commit below (a branch can move). To change it: commit to the forks' pdscenes branches, put the new
# pd-for-android commit and version here (also in the fork's build.gradle files), run this, update the app's
# dependency, commit third_party/maven. Needs git, JDK 21 (~/.jdks/jbr-21.0.11), the Android SDK and NDK 29.0.14206865.
set -e
COMMIT=2eb5545e4d6ec0f89ae5b26da08291dc9c94b81e
VERSION=1.4.2-pdscenes.1
REPO=https://github.com/dadcraftttv/pd-for-android.git
H="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$H")"
D="$H/.pdcore/pd-for-android"
[ -x "$JAVA_HOME/bin/javac" ] || JAVA_HOME="$HOME/.jdks/jbr-21.0.11"; export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
mkdir -p "$H/.pdcore"
[ -d "$D/.git" ] || git clone -q "$REPO" "$D"
cd "$D"
git fetch -q origin
git checkout -q "$COMMIT"
git submodule sync -q --recursive
git submodule update -q --init --recursive
echo "sdk.dir=$ANDROID_HOME" > local.properties
grep -q "version = '$VERSION'" PdCore/build.gradle || { echo "PdCore/build.gradle doesn't say $VERSION"; exit 1; }
rm -rf PdCore/pd-core/build/repos
./gradlew -q :PdCore:pd-core:assembleRelease
# (separately: in one run Gradle refuses the publish task, which uses the aar without declaring it needs it)
./gradlew -q :PdCore:pd-core:publishMavenPublicationToLocalRepository
OUT="$ROOT/third_party/maven/io/github/libpd/android/pd-core"
rm -rf "$OUT/$VERSION"
mkdir -p "$OUT"
cp -r "PdCore/pd-core/build/repos/releases/io/github/libpd/android/pd-core/$VERSION" "$OUT/"
cp PdCore/pd-core/build/repos/releases/io/github/libpd/android/pd-core/maven-metadata.xml* "$OUT/"
echo "pd-core $VERSION built from $REPO $COMMIT:"
sha256sum "$OUT/$VERSION/pd-core-$VERSION.aar"
