#!/usr/bin/env bash
# Starts the desktop version from the app menu (no terminal): one copy at a time (a second one would play into
# "PdScenes" twice), its messages kept in ~/.local/state/pdscenes/desktop.log (the one before in desktop.log.1).
H="$(cd "$(dirname "$0")" && pwd)"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/pdscenes"
mkdir -p "$STATE"
exec 9>"$STATE/running.lock"
if ! flock -n 9; then
    notify-send -i audio-x-generic "PdScenes" "PdScenes is already running." 2>/dev/null || true
    exit 0
fi
[ -f "$STATE/desktop.log" ] && mv -f "$STATE/desktop.log" "$STATE/desktop.log.1"
"$H/run.sh" "$@" > "$STATE/desktop.log" 2>&1
status=$?
if [ $status -ne 0 ] && [ $status -ne 130 ] && [ $status -ne 143 ]; then
    zenity --error --title="PdScenes" --width=420 \
        --text="PdScenes stopped with an error. The details are in $STATE/desktop.log" 2>/dev/null || true
fi
