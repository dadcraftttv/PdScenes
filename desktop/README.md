# PdScenes desktop (stream mode)

The phone app on Linux, as background music for a stream: the same built-in patch and the phone's own logic
(settings, presets, movers, Realms, Intensity, Calm builds, motifs, call and response), fed by your mic and, if
you like, your computer's own sound, playing into a virtual output called **PdScenes** that OBS records. No
sensors and no walking: the beat keeps the tempo you set (Music tab, Rhythm, Set tempo), and the Realms follow the
room's loudness and the time of day.

## Run it

    desktop/run.sh                  # the window
    desktop/run.sh --no-window      # just the sound; typed lines change things ("wet 0.3", "mic_device AudioBox")

The first start connects no mic: pick yours in **Setup > Listening and playing** (the mic itself, not an effects
chain's output such as EasyEffects': a mic that arrives already limited sounded overdriven through the patch).
Everything you set is kept in `~/.config/pdscenes`; saved presets are in `~/.local/share/pdscenes/presets`, in the
phone app's own format, so **Presets > Export current sound** writes a file the phone imports and **Import file**
reads one the phone exported. Desktop differences from the phone: the compressor starts off and the tempo starts
on Set; settings that need a phone (pocket, handling, following your steps) are hidden; Kinetic, Pocket and
Unstable never come (they need walking, a pocket or a shake). Not here yet: the movers' own controls (presets
bring theirs), stem packs and scenes.

The first run builds what it needs (`desktop/fetch_libs.sh`: libpd's Java connection from `tools/.libpd`, built by
`tools/build_libpd.sh`, plus JNAJack, JNA and org.json from Maven Central, checked by SHA-1). `desktop/test.sh` runs
the desktop's logic tests (presets both ways, settings kept).

## In OBS

Add a source **Audio Output Capture** and pick the device **PdScenes** (it is there while PdScenes runs). To hear it
yourself, tick Setup's "Also play to my headphones", or set that OBS source's audio monitoring to "Monitor and
Output" (Edit > Advanced Audio Properties), but not onto the output the game sound is taken from (see below).

## It never hears itself

PdScenes plays only to its own output, and that output is never offered as an input. "Also play to my headphones"
is refused while the game sound is taken from that same output (checked again whenever a device comes back).
One loop it can't see: OBS's audio monitoring of PdScenes playing to the output the game sound is taken from. If
you want game sound, give the game its own output (a virtual sink) and take the game sound from that one. Your
voice reaches the stream through PdScenes as well (its Dry level): set Dry to 0 if OBS already carries your mic.

Needs PipeWire with its JACK layer (`pipewire-jack`; the app starts under `pw-jack`), Java 21, and `pactl`.
