#!/usr/bin/env bash
# Parallel test runner: see tools/run_tests.py (no arguments = everything, `quick <words>`, `list`).
exec python3 "$(dirname "$0")/run_tests.py" "$@"
