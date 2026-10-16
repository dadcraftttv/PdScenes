# PdScenes desktop (stream mode)

The phone app's sound engine on Linux, as background music for a stream: the same built-in patch, fed by your mic
and, if you like, your computer's own sound (a game), playing into a virtual output called **PdScenes** that OBS
records. No sensors and no walking: set a tempo instead. Work in progress: step 1 (the engine) is here, the control
window comes next.

## Run it

    desktop/run.sh                                  # your default mic in, out to "PdScenes"
    desktop/run.sh --game                           # also hear the computer's sound (the default output's monitor)
    desktop/run.sh --set wet=0.3 --set beat_level=0.5 --set tempo_mode=1 --set tempo_bpm=90

Settings use the phone app's ids (see `app/src/main/java/app/pdscenes/Params.java`). Stop with Ctrl+C.
The first run builds what it needs (`desktop/fetch_libs.sh`: libpd's Java connection from `tools/.libpd`, built by
`tools/build_libpd.sh`, plus JNAJack, JNA and org.json from Maven Central, checked by SHA-1).

## In OBS

Add a source **Audio Output Capture** and pick the device **PdScenes**. To hear it yourself, set that source's audio
monitoring to "Monitor and Output" (Edit > Advanced Audio Properties).

## It never hears itself

PdScenes plays only to its own output. That output is never offered as an input, and `--listen` (also playing to
your speakers) is refused while the game sound is taken from those same speakers. Your voice reaches the stream
through PdScenes as well (its Dry level): set `dry=0` if OBS already carries your mic.

Needs PipeWire with its JACK layer (`pipewire-jack`; the app starts under `pw-jack`), Java 21, and `pactl`.
