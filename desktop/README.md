# PdScenes desktop (stream mode)

The phone app's sound engine on Linux, as background music for a stream: the same built-in patch, fed by your mic
and, if you like, your computer's own sound (a game), playing into a virtual output called **PdScenes** that OBS
records. No sensors and no walking: set a tempo instead. Work in progress: step 1 (the engine) is here, the control
window comes next.

## Run it

    desktop/run.sh --mic AudioBox --listen          # your AudioBox mic, out to "PdScenes" and your headphones
    desktop/run.sh --mic AudioBox --game            # also hear the computer's sound (the default output's monitor)
    desktop/run.sh --mic AudioBox --set wet=0.3 --set beat_level=0.5 --set tempo_mode=1 --set tempo_bpm=90

`--mic` takes a device's name or any part of its name or description ("AudioBox"); without it the system's default
input is used, and an unknown name lists the mics there are. Take the mic itself rather than an effects chain's
output (EasyEffects): a mic that arrives already limited to full scale sounded overdriven through the patch. The
phone's compressor is off on the desktop (`comp_thresh` 0; `--set comp_thresh=-30` brings it back).

Settings use the phone app's ids (see `app/src/main/java/app/pdscenes/Params.java`). While it runs, type a name and
a number to change things live: `mic 0.5`, `game 0.5`, `gain 1`, `wet 0.3`. Stop with Ctrl+C.

The mic, the game sound and the outputs are checked every 2 s: a USB interface reconnecting or EasyEffects
restarting no longer cuts the engine off; it says "Lost the mic" and "Reconnected the mic".
The first run builds what it needs (`desktop/fetch_libs.sh`: libpd's Java connection from `tools/.libpd`, built by
`tools/build_libpd.sh`, plus JNAJack, JNA and org.json from Maven Central, checked by SHA-1).

## In OBS

Add a source **Audio Output Capture** and pick the device **PdScenes**. To hear it yourself, set that source's audio
monitoring to "Monitor and Output" (Edit > Advanced Audio Properties).

## It never hears itself

PdScenes plays only to its own output. That output is never offered as an input, and `--listen` (also playing to
your speakers) is refused while the game sound is taken from those same speakers (checked again whenever a
device comes back). Your voice reaches the stream
through PdScenes as well (its Dry level): set `dry=0` if OBS already carries your mic.

Needs PipeWire with its JACK layer (`pipewire-jack`; the app starts under `pw-jack`), Java 21, and `pactl`.
