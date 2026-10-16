#!/usr/bin/env bash
# Puts PdScenes in the app menu (Sound & Video), so it starts without a terminal. Run it again after moving the
# project folder. Remove with: rm ~/.local/share/applications/pdscenes-desktop.desktop
set -e
H="$(cd "$(dirname "$0")" && pwd)"
D="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$D"
cat > "$D/pdscenes-desktop.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=PdScenes
GenericName=Reactive music
Comment=Turns your mic into music for your stream (plays to the PdScenes output for OBS)
Exec="$H/launch.sh"
Icon=audio-x-generic
Terminal=false
Categories=AudioVideo;Audio;
StartupWMClass=app-pdscenes-DesktopApp
DESKTOP
desktop-file-validate "$D/pdscenes-desktop.desktop" 2>/dev/null || true
update-desktop-database "$D" 2>/dev/null || true
echo "PdScenes is in the app menu (Sound & Video)."
