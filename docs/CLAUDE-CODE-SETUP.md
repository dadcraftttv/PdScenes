# Setting up Claude Code on the build machine

One-time setup so Claude can build, install and debug the app itself.

1. **Put the project on the machine** (the same folder Android Studio opens). If it is not a git repo yet:
   `cd PdScenes && git init && git add -A && git commit -m "Initial import"`.
2. **Install Claude Code.** In a terminal run `curl -fsSL https://claude.ai/install.sh | bash`, then open a new terminal and check
   `claude --version`. If it says "command not found", add `~/.local/bin` to PATH:
   `echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc`. Then run `claude` inside the project folder and sign in through the browser
   (needs a Pro, Max, Team, Enterprise or Console account). It updates itself. Alternatives: the apt repository, or `npm install -g @anthropic-ai/claude-code`.
   Details: https://code.claude.com/docs/en/setup
3. **Make adb available.** Android Studio installs it at `~/Android/Sdk/platform-tools`. Add it to PATH:
   `echo 'export PATH=$PATH:$HOME/Android/Sdk/platform-tools' >> ~/.bashrc`, open a new terminal, check `adb version`.
4. **Connect the phone.** USB works. For wireless: Settings > Developer options > Wireless debugging > Pair device with pairing code, then
   `adb pair <ip:port>` and `adb connect <ip:port>`. Check `adb devices` shows it as `device` (not `offline`).
5. **Tell Gradle where the SDK is** if it is not already: a `local.properties` file with `sdk.dir=/home/<you>/Android/Sdk`
   (Android Studio writes this itself; it is git-ignored).
6. **Check the build:** `./gradlew assembleDebug` (first run downloads a lot; it needs internet for the pd-core snapshot).
7. **Optional, for the Pd audio tests:** `sudo apt install git make gcc python3 default-jdk`, then `tools/build_libpd.sh`.
8. Start `claude` in the project folder. It reads `CLAUDE.md` automatically. A good first message:
   "Build the debug APK, install it on my connected phone, and tell me what to listen for."

Tips: keep Android Studio closed or at least not mid-Gradle-sync while Claude runs builds. If the phone shows `offline` in `adb devices`,
reconnect the cable or re-run `adb connect`. Release signing keys and Play Console credentials should never be put in the repo.
