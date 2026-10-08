#!/usr/bin/env bash
# Runs the plain-Java logic tests (no Android needed). Usage: tools/javatests/run.sh [M N W R C P P2 T S E X]
# Android classes are replaced by tiny stubs in stubs/ and stubs2/.
set -e
export JAVA_TOOL_OPTIONS=
H="$(cd "$(dirname "$0")" && pwd)"; SRC="$H/../../app/src/main/java/app/pdscenes"
CORE="$SRC/Param.java $SRC/Params.java $SRC/ParamStore.java $SRC/PresetManager.java $SRC/Modulation.java $SRC/PhoneContext.java"
for t in "${@:-M N W R C P P2 T S E X}"; do for x in $t; do
  extra=""; [ "$x" = W -o "$x" = X ] && extra="$SRC/StepDetector.java $SRC/WorldSelector.java $SRC/Worlds.java"
  [ "$x" = E ] && extra="$SRC/SceneEvents.java"
  [ "$x" = C ] && extra="$SRC/SensorInput.java $SRC/StepDetector.java"
  [ "$x" = P2 ] && extra="$SRC/SensorInput.java $SRC/StepDetector.java $SRC/ScenePad.java $SRC/SceneLibrary.java"
  [ "$x" = S ] && extra="$SRC/SceneLibrary.java"
  [ "$x" = X ] && extra="$extra $H/test/M.java"
  out=$(mktemp -d)
  javac -d "$out" -proc:none -cp "$H/stubs:$H/stubs2" $CORE $extra "$H/test/$x.java" 2>&1 | grep -v "^Note:" || true
  echo "== $x"; java -cp "$out:$H/stubs:$H/stubs2" app.pdscenes.$x
done; done
