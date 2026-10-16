# PdScenes desktop (stream mode)

The phone app on Linux, as background music for a stream: the same built-in patch and the phone's own logic
(settings, presets, movers, Realms, Intensity, Calm builds, motifs, call and response), fed by your mic and, if
you like, your computer's own sound, playing into a virtual output called **PdScenes** that OBS records. No
sensors and no walking: the beat keeps the tempo you set (Music tab, Rhythm, Set tempo), and the Realms follow the
room's loudness and the time of day.

## Run it

    desktop/install-launcher.sh     # once: puts PdScenes in the app menu (Sound & Video), no terminal needed
    desktop/run.sh                  # the window, from a terminal
    desktop/run.sh --no-window      # just the sound; typed lines change things ("wet 0.3", "mic_device AudioBox")

From the menu (`desktop/launch.sh`) one copy runs at a time (a second start says so), and its messages go to
`~/.local/state/pdscenes/desktop.log` (the run before in `desktop.log.1`).

The first start connects no mic: pick yours in **Setup > Listening and playing** (the mic itself, not an effects
chain's output such as EasyEffects': a mic that arrives already limited sounded overdriven through the patch).
Everything you set is kept in `~/.config/pdscenes`; saved presets are in `~/.local/share/pdscenes/presets`, in the
phone app's own format, so **Presets > Export current sound** writes a file the phone imports and **Import file**
reads one the phone exported. Desktop differences from the phone: the compressor starts off and the tempo starts
on Set; settings that need a phone (pocket, handling, following your steps) are hidden; Kinetic, Pocket and
Unstable never come (they need walking, a pocket or a shake). Not here yet: the movers' own controls (presets
bring theirs). Stem packs and scenes stay on the phone.

Tip: in a quiet room a desktop mic's faint hiss gets echoed too, and with Echo scatter that hiss hops from ear to
ear. Raise **Sound > Input & output > Noise gate threshold** (around -55 dB) so the gate closes between sounds.

The first run builds what it needs (`desktop/fetch_libs.sh`: libpd's Java connection from `tools/.libpd`, built by
`tools/build_libpd.sh`, plus JNAJack, JNA and org.json from Maven Central, checked by SHA-1). `desktop/test.sh` runs
the desktop's logic tests (presets both ways, settings kept).

## In OBS

Add a source **Audio Output Capture** and pick the device **PdScenes** (it is there while PdScenes runs). To hear it
yourself, tick Setup's "Also play to my headphones", or set that OBS source's audio monitoring to "Monitor and
Output" (Edit > Advanced Audio Properties), but not onto the output the game sound is taken from (see below).

## Game sound

Setup > **Also hear a game**: start the game, press **Look for devices again**, and pick it under **Taken from**
("App: ..."). PdScenes then hears the game's own sound (like OBS's Application Audio Capture): only the game, not
Discord or alerts, with no delay added to what you hear, and it reconnects when you restart the game. A **whole
output** (everything heard on it) can be picked too, but that can loop (below).

## It never hears itself

PdScenes plays only to its own output, and that output is never offered as an input. "Also play to my headphones"
is refused while the game sound is taken from that same output (checked again whenever a device comes back).
One loop it can't see: OBS's audio monitoring of PdScenes playing to a whole output the game sound is taken from.
Taking the game itself (an app) never loops. Your
voice reaches the stream through PdScenes as well (its Dry level): set Dry to 0 if OBS already carries your mic.

Needs PipeWire with its JACK layer (`pipewire-jack`; the app starts under `pw-jack`), Java 21, and `pactl`.
