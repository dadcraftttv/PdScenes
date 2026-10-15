# Beta Tester Guide

Oct 14, 2026 · Dad · for 0.9.0-rc2

## What this app is

This app listens to the world through your phone's microphone, changes the sound as you hear it, and plays the result into your headphones in real time. Clap, talk, or walk around, and the sound you hear is a twisted, echoing, wobbling version of your surroundings. It can also turn the sounds around you into music: a beat made from your claps and knocks, melodies played on them, and chords sung by your own hum.

It is a free, open-source homage to RjDj, an older iPhone app that made "reactive music" this way. The app is still unfinished and has no final name yet, so expect rough edges. That is what this test is for.

There are two ways to use it:

- **Built-in effects (the default).** A set of sound-changing tools you can adjust with sliders. Most of this guide covers these.
- **Scenes (optional).** Ready-made experiences from the original RjDj, which react to sound and to how you move the phone. The app comes with four official RjDj example scenes to try (see "The four built-in scenes" below). You can also import other scenes you already have, as a zip file or folder.

## What's new

**Oct 15 (in the next test build):**

- **Melody rhythm** (Music): the walking notes and the standing-still chimes can follow real rhythms (quarters, halves, 8ths, or dotted and syncopated ones), each note ringing as long as it lasts. Off at first.
- **Melody phrases** (Music, with Melody rhythm on): the melody makes four-bar phrases: a line, the line again ending like an answer, something new, then the first line once more.
- **Breakbeat** (Rhythm): turn it up for drums with off-beat kicks, ghost snares, now and then a chopped bar, a quick snare roll or a longer fill. At 0 the beat is as before.

**Oct 13-14:**

- **Call and response** (Music): sing, hum or whistle a short phrase, pause, and the app answers it with chimes, a third away, in key.
- **Send feedback** (Setup, About): writes an email to Dad with your phone and app details and, if you like, the app's event log.
- **Stem packs** (Music tab): your own loops, playing with the built-in sound and arranged by where you are and how you move.
- **Calm builds** (Music, off at first): standing still somewhere calm, the music slowly grows a layer at a time, then eases back.
- **Scenes show their pictures and words** on the touch pad, and a few more imported scenes load completely.
- **Reverse reverb** (Reverb section, and in the Ghost realm): sounds come back as rising swells, landing on the beat while the Rhythm plays.
- **Mix** (Music tab): a level for every part of the music and rhythm, saved with your presets, so you can turn any part down or out.
- **Intensity** in the bottom card: calmer to the left, busier to the right, your own settings in the middle.
- **Handling noise:** tapping, gripping or rubbing the phone no longer becomes part of the music: those sounds are turned down and never caught as found sounds (see Handling hush).
- **Diagnostics** on the Setup tab shows which mic and headphones are really in use, how loud the mic hears the room, and whether anything overloads. If the mic itself keeps overloading, the status line at the bottom says so.
- **Welcome pages** on a new install, and **a quiet start**: a new install has everything off (the echo too), so you hear only the room until you turn things on.
- **Dry level no longer turns the music down:** it only changes your microphone's sound.

**Oct 12:**

- **Five tabs** instead of one long list: Sound, Music, Realms, Scenes and Setup, switched from the row at the top of the card at the bottom of the screen.
- **Realms** (formerly called Auto worlds): the same automatic sound changes, renamed. Each Realm can now be told which parts of the sound it may change, and a soft "warp" sound tells you when a Realm starts or ends.
- **Rhythm** (was "Walking beat"): a steady tempo clock that follows your steps or a tempo you set, beat patterns that keep changing, and drums made from the sounds around you.
- **Found sounds everywhere:** the melody, the chimes, the room's ringing notes, the pad chords and (if you want) the bass can all be played with sounds the app caught from your surroundings.
- **Your voice as the harmony:** hum or sing a note and a copy of your own voice answers on a chord note.
- **Gate and compressor shape** settings for the microphone.
- **Music stays in time** with the beat, standing or walking.
- A small dot shows which sliders a mover is moving.
- The Key and Scale menus no longer jump back to C major.
- The app uses noticeably less battery and processor than the first builds with these features.

## Permissions and privacy

The app does not collect, store, or send any of your data. It has no internet permission at all, so it cannot send anything off your phone even if it wanted to. There are no accounts, ads, or tracking. Your microphone sound is processed live on the phone and never recorded to a file. The "found sound" features keep a few short snippets (a clap, a knock, a held hum, each under a second) in the phone's working memory while the app plays. They are never saved, and they are gone when you press Stop.

What it asks for, and why:

| Permission | What it is for |
| --- | --- |
| Microphone | The whole point: it needs to hear the sound in order to change it. Android asks the first time you press Start. |
| Notifications | Android requires a visible notification whenever an app is using the microphone in the background. It reads "is listening" while the app runs. |
| Run in the background (foreground service) | Lets the sound keep playing when you lock the screen or switch apps. Press Stop to end it. |
| Change audio settings | Lets the app pick the right audio route, such as headphones. |

The app also reads the phone's motion sensors (tilt, shake, spin, compass heading, steps). Android does not ask permission for these. They only steer the sound on your phone, and nothing is saved or sent.

Presets and scenes you save or import stay in the app's private storage on your phone. You choose where an exported preset file goes. To remove everything, uninstall the app.

## Getting started

You need an Android phone or tablet with **Android 9 or newer**, and headphones or earbuds.

1. **Put on headphones first.** If the sound comes out of the phone speaker, the microphone hears it and it screeches back (feedback). The app only plays into headphones or earbuds, never the phone speaker, so it will not start until some are connected. If you unplug them while it runs, it stops by itself. Wired or Bluetooth both work; wired is better (see Audio devices below).
2. Install the APK. If you already have an earlier copy, just install over it; your saved presets and settings stay. Only if Android refuses with "App not installed" do you need to uninstall the old copy first (see "Starting fresh with Reset" for what that erases). Android may ask you to allow installs from the app you opened it from, and Play Protect may show an "unknown developer" warning. Choose **More details > Install anyway**.
3. Open the app. On a new install a few short welcome pages explain the basics and ask for the microphone (you can see them again under Setup, About). Then press **Start**, in the card at the bottom of the screen.
4. **It starts quiet, on purpose.** A new install has everything switched off, so at first you hear only the world around you through your headphones. Turn one thing on, listen to what it does, then try the next: Echo level on the Sound tab, Beat level and Music on the Music tab, Auto realms on the Realms tab, and Intensity in the card. If you hear nothing at all, try raising **Input gain** under Input & output. (If you already had an earlier copy installed, your settings stay as they were.)
5. Press **Stop** when finished.

Start with the volume low. Some settings can get loud.

## The main screen

The screen has five tabs. The **card at the bottom** stays in place on every tab, in reach of your thumb when you walk:

- **The tab row** across the top of the card: **Sound**, **Music**, **Realms**, **Scenes** and **Setup**. The tab you are on is highlighted. Each tab keeps its own place when you scroll, and the app opens on the tab you used last.
- **The status line** says what is happening, including the audio rate your phone is using. Under it a **Now:** line shows the Realm playing and why (see The Realms tab), and while the Rhythm plays, the tempo ("walking 112 BPM") and the found-sound kit ("kit K2 S1 H3 · 24 caught": how many kicks, snares and hats it holds, and how many sounds it has caught in all).
- **Intensity**: one slider for how much is going on. In the middle (50) everything plays exactly as you set it. Slide left for calmer: fewer glitches and chimes, less echo and reverb, quieter and simpler drums, lighter effects. Slide right for busier: more of all of those and busier drum patterns. It only turns up what is already on (an effect you set to 0 stays off), it never changes your sliders, and presets and Realms leave it alone. The same slider sits at the top of Input & output, where you can also give it a mover (for example Shake = higher). It is hidden while a scene plays.
- **Start / Stop**, **Save sound** (keeps the sound you are hearing as a preset in one tap) and **Hold realm** (appears when Auto realms is on).

Inside a tab, settings are grouped in sections. Tap a section's heading to open or fold it; the app remembers which ones you opened. While a scene is playing, the Sound, Music and Realms tabs say so instead of showing controls that would do nothing.

| Tab | What is on it |
| --- | --- |
| Sound | Presets and shortcuts, the XY pad, Input & output, and all the effects |
| Music | Rhythm and Music |
| Realms | Auto realms: the sound changing by itself to fit where you are |
| Scenes | Choosing and importing scenes, the scene's touch pad, its volume sliders |
| Setup | Audio devices, diagnostics, appearance, behavior, Reset everything, About |

## The Sound tab

At the top: **Presets**, **Save**, **Export** and **Import**, then **Randomize**, **Nudge** and **Undo** (see Presets and shortcuts), and the **XY pad**, a rounded rectangle you can drag a finger around to steer sliders (see Movers). Below them are Input & output and the effects.

An "effect" is a way of changing a sound. The sound flows through them in a chain, so you can use several together. Each effect lives in its own section, which you open and close by tapping its title. Each has an on/off switch, and an amount slider. The amount is usually at 0 to start, so an effect does nothing until you turn its amount up. Move one slider at a time and listen.

The numbers (ms, Hz) don't matter much. Drag, listen, and decide whether you like it.

### Input & output

This section controls the sound going in, before any effect touches it.

- **Intensity:** the same control as in the bottom card (see The main screen).

- **Input gain:** the microphone's volume. Turn it up if everything is too quiet, down if it's harsh or distorts.
- **Noise gate threshold:** silences very quiet sounds, like background hiss, so only louder sounds come through. At the far left it is off.
- **Compressor threshold, ratio, make-up gain:** evens out loud and quiet sounds so nothing jumps out. Threshold at 0 turns it off. It starts switched on, set to balance things gently, and Input gain starts fairly high so quiet details are picked up. Change either if you like. Ratio is how firmly it squeezes the loud parts, and make-up gain is how much volume you give back afterward.
- **Pocket hush:** while the phone is in a pocket, the microphone is turned down so cloth rustle doesn't swamp the sound, and rustle doesn't set off chimes. Your drums and the music play as normal. Higher hushes more. At 0 nothing changes. If you can't hear the world from your pocket, lower it. If the rustle is too loud, raise it.
- **Handling hush:** when you tap, grip, rub or fiddle with the phone, its microphone hears that loudly. The app feels it through the phone's motion and turns the mic down while it lasts (higher hushes more; at 0 nothing changes). Whatever this is set to, those taps and scrapes never set off chimes or glitches and are never caught as found sounds. Walking with the phone in your hand doesn't count as handling, and neither do claps or knocks around you, because the phone itself doesn't move with them.
- **Mic-down protection:** extra help only when the phone is in your pocket with the microphone end (the bottom edge) going in first, where it rubs against more fabric. It filters out the low thump of cloth and turns the mic down a little more. Mic end up is left alone. At 0 nothing changes.
- **Dry level:** how much of your original, untouched sound you hear alongside the effects. Lower it to hear mostly effects. It only changes your microphone's sound: the music keeps its own levels, and the echo keeps repeating your sound even with Dry all the way down.

**Gate and compressor shape** (its own folded section) fine-tunes how the noise gate and compressor react. The defaults open the gate within a few milliseconds of a sound and let it fade smoothly, so you don't need to touch these.

- **Gate attack:** how quickly the gate opens when a sound starts.
- **Gate hold:** how long it stays open after the sound drops below the threshold.
- **Gate release:** how slowly it fades closed. Longer sounds smoother; shorter is tighter.
- **Compressor attack and release:** how quickly the compressor turns loud sounds down, and how quickly it lets them back up.

Right at the end of the chain there is also a built-in safety limiter. It gently rounds off sudden loud peaks so the sound stays smooth instead of turning fuzzy or crackly. It has no controls; it just works quietly in the background. If you still hear fuzziness, try lowering Input gain a little.

### Echo

Repeats what you said, like shouting in a canyon.

- **Echo time:** how long before the repeat comes back. Short is a metallic ring, long is a distinct repeat.
- **Echo follows your steps:** while you walk, the repeats lock to your step rhythm: 1 step, Half a step (the default) or a Quarter step. About 2.5 seconds after you stop, Echo time takes over again. Choose Off to always use Echo time.
- **Echo scatter:** each repeat lands somewhere else between your ears, so a clap's echoes bounce around you. 0 keeps the echo in the middle. It starts at 0.5.
- **Echo feedback:** how many times it repeats. Too high and it never dies away.
- **Echo level:** how loud the repeats are. It starts at 0 on a new install (no echo); raise it to hear the echo.

### Ring modulator

A robotic, metallic, "Dalek" kind of sound.

- **Ring-mod frequency:** the pitch of the metallic buzz. Low sounds growly, high sounds bell-like.
- **Ring-mod amount:** how much of the effect you hear.

### Pitch shifter

Makes your voice higher (chipmunk) or lower (monster).

- **Pitch shift amount:** how far to move it. Each step is a note on a piano. Negative is lower, positive is higher.
- **Pitch shift mix:** 0 is just you, 1 is just the shifted voice. Halfway gives you a harmony.
- **Pitch grain size:** a technical setting that trades smoothness against delay. Leave it unless the sound is warbly.

### Bit crusher

Makes the sound crunchy and lo-fi, like an old video game or a bad phone line.

- **Bit-crush amount:** how much you hear.
- **Bit depth:** lower numbers are grittier and noisier.
- **Sample-rate reduction:** lower numbers make the sound grainy and muffled, with a metallic edge.

### Distortion

Dirty, fuzzy, overdriven sound, like a rock guitar.

- **Distortion amount:** how much you hear.
- **Distortion drive:** how hard the sound is pushed. Higher is more aggressive.
- **Distortion type:** Soft clip is warm and fuzzy. Hard clip is harsher. Wavefold is a strange, buzzy, electronic sound.

### Filter

Lets some sounds through and blocks others, like turning the bass or treble knob way up or down.

- **Filter amount:** how much you hear.
- **Filter type:** Low-pass removes the high sounds, which makes things muffled, as if behind a wall. High-pass removes the low sounds, which makes things thin, like a small radio. Band-pass keeps only a narrow slice, which gives a telephone sound.
- **Filter frequency:** where the cut happens.
- **Filter resonance:** adds a whistling edge at the cut point. High values give a wah-wah or squeal.

### Chorus

Makes one voice sound like several people singing together slightly out of step.

- **Chorus amount, speed, depth:** how much, how fast the wobble moves, and how far the voices drift apart.

### Flanger

A whooshing, jet-plane sweep.

- **Flanger amount, speed, depth:** how much, how quickly the sweep goes up and down, and how wide it is.
- **Flanger feedback:** how intense the whoosh is. Negative values give a hollow, tube-like sound.

### Phaser

Similar to a flanger but softer and more swirling, like a spinning, space-age sound.

- **Phaser amount, speed, sweep width, feedback:** how much, how fast it swirls, how wide it sweeps, and how intense it is.

### Tremolo

Makes the volume pulse up and down rapidly, like a shaky voice or a helicopter.

- **Tremolo depth:** how deep the pulsing is. 0 is off.
- **Tremolo speed:** how fast it pulses.

### Reverse echo

Plays little chunks of what you just said, backward.

- **Reverse echo level:** how loud the reversed chunks are.
- **Reversed chunk length:** how long each backward chunk is.

### Glitch

Two kinds of glitch live here: the glitch cloud, which throws bits of what just happened back at you, and the older freeze, which holds the sound like a skipping CD.

**The glitch cloud.** The app keeps the last few seconds of what the mic hears in memory only (nothing is ever saved). A sudden sound, like a clap, a door or a laugh, comes back mangled, and each glitch lands somewhere different around your head. When nothing sudden happens, a slow clock now and then glitches a random bit of the last few seconds. While you walk, glitches wait for your next step or half-step so they land on the beat. With the Rhythm on, each glitch also comes back as a loop inside the beat (see Rhythm).

- **Glitch cloud amount:** how often a glitch gets its chance. 0 (the default) switches the glitch cloud off.
- **Glitch cloud level:** how loud the glitches are.
- **The glitch matrix:** four sliders share out the chances between the kinds of glitch. **Stutter** repeats a slice of the sound (a quarter step long while you walk), **Reverse** plays it backwards, **Shuffle** brings back an older moment out of order, and **Stretch** smears it out slowly while the pitch stays the same. Together they can't go past 100%: a slider stops at whatever the others leave free. Whatever you leave unassigned is silence, so Reverse 10% and Shuffle 10% means 80% of the chances pass with nothing happening. The bold **Glitch budget** line under the sliders shows how much is used and how much is left to silence. They start at Stutter 35, Reverse 25, Shuffle 20, Stretch 20.

* **Freeze:** 0 is live sound. At 1, the last moment is looped and held.
* **Freeze loop length:** how long the looped piece is. Shorter is more robotic.

### Reverb

Makes it sound like you're in a bigger space, like a church, a bathroom, or a cave.

- **Reverb level:** how much of the room sound you hear.
- **Room size:** small room or huge hall.
- **Reverb brightness:** a bright, glassy room or a soft, dark one.
- **Reverse reverb:** a sudden sound comes back a moment later as its own echo played backwards: a ghostly swell that rises out of nothing and stops right where the sound began. While the Rhythm plays, each swell is one beat long and lands on a beat; otherwise it comes about two seconds later (longer in a bigger room). It needs the Reverb level up. 0 turns it off.

### Spatial

Places the sound in your headphones.

- **Pan:** all the way left, all the way right, or in the middle.
- **Ear delay:** delays one ear slightly, which tricks your brain into hearing the sound as coming from the side.

## The Music tab

Everything that turns the room into music: the Rhythm (the beat) and the Music (notes, chords and harmony).

### Rhythm

A beat that plays along with you. It used to be called "Walking beat", but it now does much more than follow your feet: it keeps a steady tempo, plays changing drum patterns, and can build its drum kit out of the sounds around you.

**The tempo.** A steady clock keeps the beat. While you walk, it follows your steps the way a band follows its drummer: an odd step barely moves it, a change of pace is followed within a few steps, and a slow amble plays at double time. When you stop, the beat carries on at the last tempo.

- **Rhythm enabled:** the switch for the whole section.
- **Beat follows:** **Tempo clock** (the default, steady) or **Your steps** (the older behavior: one drum hit per footstep, wobbles and all).
- **Tempo:** **Auto** (the default) follows your steps as described. **Set** lets you choose the tempo yourself with **Set tempo**, from 60 to 160 BPM: standing still the beat settles on your tempo; walking pulls it halfway toward your step rate, so you still feel your walk; when you stop it settles back. Try around 125 for a dance feel, or down in the 80s and 90s for hip hop.
- **Beat plays:** **Always** (the default: softly while you stand still, fuller when you walk) or **Only while walking**.

**The patterns.** The drums play real patterns on 16th notes, not just one hit per step. Every couple of bars it picks new kick, snare and hat patterns to suit how lively things are (a stroll or a quiet room gets calm ones, a brisk walk or a lively room busier ones), and every eight bars or so it may end on a snare fill. To keep it from sounding mechanical:

- the swing drifts every few bars, from straight to a little lazy;
- now and then (at least eight bars apart) one bar thins out, to hats only, no kick, or just the first kick, before the full beat comes back;
- the patterns follow your pace and the room; while your steps are uneven (shuffling, turning) the drums play softer until your rhythm settles.

**Drums made from the room ("Beat sounds").**

- **Beat sounds:** **Found sounds** (the default), **Synth drums** or **Both**.
- With Found sounds, each sudden sound the phone hears (a clap, a knock, a snap, a footstep, a door) is caught as a short snippet and filed as a kick (mostly low), a hat (mostly bright) or a snare (everything else). The kit keeps the latest five of each. Your very first catch already turns the whole kit into found sounds; until then a quiet synth beat keeps time.
- Every hit is a little different: slightly higher or lower, softer or harder, sometimes with a softer start. About one hit in twenty plays backwards or at half speed, as a small surprise.
- A snap right at the microphone can overload it into a loud low pop; those are recognized and not kept. Nothing is caught while the phone is in a pocket, so cloth rustle stays out of the kit.
- **The beat learns from you:** if you clap or knock on the same spot in the bar a few times, the beat starts playing a drum there too, and lets it fade a few bars after you stop.
- **Glitch loops woven into the beat:** with the Glitch cloud on (see Glitch), each glitch is recorded for one bar and comes back in the beat at the same spot, fading bar by bar. Its level is in the Mix section; 0 turns it off.

**Levels.**

- **Beat level (0 = off):** how loud the drums are. It starts at 0, so you hear nothing until you turn it up.
- The kick, snare, hi-hat and glitch-loop levels are in the **Mix** section (below Music).
- **Kick drum pitch:** how low or high the synth kick sounds.
- **Breakbeat:** 0 (the start) leaves the beat as it was. Turn it up and the bars lean on breakbeat patterns: kicks off the beat, snares on the "and", quiet ghost snares. Now and then a bar is chopped (its pieces shuffled, the first beat kept), gets a quick snare roll, or ends in a longer fill. The higher it is, the more often. Your walking pace still sets the tempo and the hi-hats, and it works with synth and found drums alike. It is saved with presets.

### Music

This adds a soft, drifting musical layer that reacts to the world around you, in the spirit of RjDj. It is **off until you switch it on**. The notes are always in the key and scale you choose, so they always sound pleasant together, but when they play and how loud they are comes from what the app hears and how you move. Many parts can be played with sounds the app catches from your surroundings ("found sounds"); each such part has its own choice of Synth, Found sounds or Both.

- **Music on/off:** the switch for the whole section.
- **Let the home chord drift:** every few minutes the music's home chord moves to a related one on the same notes (in C major, for example, to a D, G or A-minor feel), then often comes back home. Switching it off brings the home chord back at once. On by default.
- **Light, pocket and stairs move the notes higher or lower:** in a bright place the chimes and walking notes sit a little higher, in a dark room a little lower and warmer, in a pocket an octave lower, and climbing stairs lifts them. The pad and bass stay put. On by default.
- **Calm builds:** off at first. Switch it on and, when you stand still in a calm place for about half a minute, the music slowly grows on its own, one layer at a time: the pad warms up, the room notes ring a little more, a few soft chimes start to come, then harmony and reverb open up. It takes about three minutes to reach the top, holds for a minute, eases back over two, then rests for at least three minutes before the next one. Walk, or step into a loud, lively place, and it fades away within a few seconds. It only grows parts that are already on, and never moves your sliders. The Now line says "building" while it happens. It is your own setting: presets don't save or change it.
- **Key and Scale:** the home note and the mood. It starts in C Major. Major sounds bright, Minor sounds sad or serious, Major pentatonic and Minor pentatonic are simple and open, Dorian and Mixolydian are folky, Lydian is dreamy, and Whole tone is floaty and unresolved. Try them all.
- **The pad:** a very soft, slow background of gentle chords. It blends smoothly from one chord into the next. It is meant to be the glue, never the star. Its level (Pad level) is in the Mix section; keep it low.
- **Pad register:** where the pad plays. **Low** is a soft bass note under everything that stays on the key's root and only sometimes moves. **Mid** is the chords. **Both** (the default) is the two together. When the beat is playing, the bass dips briefly on each step so it doesn't clash with the kick drum.
- **Pad sounds:** **Found sounds** (the default), **Synth** or **Both**. With Found sounds, when you hum, sing or whistle a steady note (or a steady hum from a machine or a bird), the app keeps a short snippet of it, and from the next chord change the pad's chord is sung by that sound, stretched out and pitched to each chord note. It sounds like a choir of you holding the harmony. Until the first held note it plays the synth pad.
- **Bass sound:** **Synth** (the default) or **Found sounds**, which plays the bass with that same held-note snippet, pitched down. It is subtle.
- **Notes and chimes level:** how loud the melody notes are (the chimes and the walking notes). Turn it to 0 to hear only the pad.
- **Melody rhythm:** **Off** (the start: as before), **Straight**, **Dotted** or **Mixed**. Switched on, the melody follows one-bar rhythms in time with the beat: Straight uses whole, half, quarter and 8th notes; Dotted uses dotted and syncopated ones (like a dotted quarter then an 8th, or a 3-3-2 pattern); Mixed uses both. Each bar picks a rhythm that suits how fast you walk (or how lively the room is, standing still), and each note rings as long as it lasts: a half note rings long, an 8th is short. While you walk the walking notes follow it; standing still, the chimes that come now and then land on it. Chimes set off by a sound around you are not affected.
- **Melody phrases (repeat and answer, needs Melody rhythm):** off at first. Switched on (with Melody rhythm on), the melody comes in four-bar phrases: bar 1 makes up a line, bar 2 repeats it but ends on the chord's home note like an answer, bar 3 goes somewhere new, and bar 4 brings the first line back. The rhythm repeats with the notes. The notes mostly move one step at a time, and the notes on beats 1 and 3 belong to the chord. Walking, it plays the walking notes; standing still, the chimes that come now and then (so you hear only some of the phrase).
- **Melody sounds:** **Found sounds** (the default), **Synth chimes** or **Both**. With Found sounds, the chimes and walking notes play the sounds caught for the beat, tuned to each note. Until the first catch they play synth chimes.
- **Chime character (ring to your sound):** how the found melody sounds. Toward "ring", each note is a tuned, bell-like ring set off by your sound. Toward "your sound", each note is mostly your clap, knock or snap itself played at that pitch, short and punchy. It starts in the middle.
- **Room notes:** how loud the room's own notes are.
- **Room notes sound:** **Found sounds** (the default): each sudden sound around you plays one of your caught sounds on a note of the current chord. **Ring**: the sounds around you ring the chord like a bell, in your key (a light tap gives a quick chime, talking or a passing car builds up to a long bell). **Both** plays the two.
- **Harmony:** hum, sing or whistle a long, steady note and an answering note from the current chord joins in, never doubling yours. It holds as long as your note does and fades when you stop. Talking, noise and short sounds are ignored. Its level is in the Mix section; 0 turns it off.
- **Harmony sound:** **Your voice** (the default): a copy of your own voice, shifted to the chord note, sings with you. Low voices get their harmony a third or more above; from middle C up (most women's and children's voices) it sings a third or more below, so it never turns chipmunk. **Organ** is a soft organ note an octave away instead. **Both** plays the two.
- **Call and response:** sing, hum or whistle a short phrase (one to six notes) and pause. A moment after you stop, the app answers it with chimes: the same rhythm and shape, a third higher (a third lower if you sang high), in key, sometimes ending on the home note. While the Rhythm plays, the answer falls on the beat. It answers each phrase once. Higher plays the answer louder; 0 turns it off. It needs Music on.
- **Tone:** darker and rounder on the left, brighter and glassier on the right.
- **How much the music follows what it hears:** at the right end the music responds strongly to the room. At the left it plays a calmer, steadier pattern.

What to expect:

- In a quiet room the notes stay quiet or silent. They wake up as the room gets louder.
- A sudden sound, like a clap or a door, rings a chime. A brighter sound gives higher chords.
- Standing still, you get a slow, sparse pattern. When you walk, it turns into a flowing run of notes with each step, which swells louder as you walk faster and fades as you slow down. A stroll picks calmer patterns, a brisk walk livelier ones.
- **The music stays in time with the beat.** While the Rhythm plays, chimes wait for the next half-beat (at most half a beat: about a third of a second at a walking tempo, up to half a second at the slowest set tempo) so they fall in with the drums, standing or walking. When you stop walking, the pad and bass ease down a little for a few seconds, then fill back in.
- When a lot has been played lately, the music holds back and leaves more room, so a busy room doesn't turn into a wall of notes.
- The music remembers the last little run of chimes. When the room goes quiet for a while and you are standing still, it may play that phrase back with a twist, like a theme returning.
- The music passes through your other effects, so Echo, Reverb, Chorus, Spatial and the rest all shape it. The Pitch, Ring, Bit-crush, Distortion and Filter effects do not touch it.
- In Realms, Tranquil keeps the music very soft, Flux keeps the notes light but lets the loud room ring in key, Kinetic lets the notes grow with your pace, and Pocket switches Room notes off. Realms never switch the music on or off for you.

### Stem packs (your own loops)

A stem pack is a set of loops from a song (pad, bass, drums, lead, texture) that plays with the built-in sound and follows where you are and how you move: the pad is always there, bass and drums come in when you walk, the lead in a lively place or on a brisk walk, the texture at night, in a pocket or in the Ghost realm. Parts change only at the start of a bar, fading over one bar, and if the pack has sections (like a verse and a chorus) it moves between them every few loops.

- **Choose pack** picks the pack that plays (or None). **Import zip** and **Import folder** add one. **How to make a pack** explains the format. **Delete a pack** removes one from the phone.
- While a pack plays, the tempo locks to the pack's tempo (walking changes which parts play, not the tempo), the chimes, pad and harmony follow the pack's key, and the app's own beat steps back while the pack's drums play. Your own settings come back when you choose None.
- **Stems level** (in Mix) sets how loud the pack is.
- Packs only play with the built-in sound, not with scenes. A pack can have up to 8 loops, together at most 4 minutes of stereo audio, because the whole pack is held in memory while it plays.

### Mix

One place to set how loud each part of the music and rhythm is, so you can turn any part down or take it out completely (0). The Mix is saved with your presets, so a preset you share carries your mix along with everything else. (Presets made before the Mix keep whatever mix you have.)

- **Kick, Snare, Hi-hat:** each drum on its own, synth and found alike. **Glitch loops woven into the beat:** the glitch bars in the beat.
- **Pad level:** the soft chords. **Bass:** the low note under the pad.
- **Chimes:** the notes set off by sudden sounds, the slow standing-still pattern and remembered phrases coming back. **Walking notes:** the run of notes with your steps and the groove note.
- **Room notes: ring** and **Room notes: found bells:** the two kinds of room notes (see Room notes sound), each on its own.
- **Harmony:** the answering note.

The ones marked with an "x" (Kick, Bass, Chimes, Walking notes and the two room-note levels) are new. They sit inside their group's own level: Beat level still turns all the drums up or down together, Notes and chimes level all the melody notes, Pad level the pad and bass, Room notes both room-note kinds. Each starts at 1 (as before) and goes from 0 (out) to 1.5 (half as loud again).

## Movers: sliders that move on their own

A mover is a hands-free way to change a slider. Instead of dragging it yourself, a mover pushes it up and down around the spot where you left it. Under every slider is a **Movement** menu. It is set to Off until you choose something.

**To use one:**

1. In the section's header area, turn on **Movers (automatic movement) for this section**. Each section has one of these switches. While it is off, that section's mover menus are grayed out and do nothing.
2. Under the slider you want to move, pick a **Movement**.
3. Two more settings appear: **Speed** (how fast it moves or reacts) and **Depth** (how far it moves). Depth 0 means no movement.

Turning the section switch off sends every slider back to where you set it, and your movement choices are remembered for next time. While the sound plays, a small dot after a slider's name shows that a mover is moving it.

**The movement choices:**

| Movement | What it does |
| --- | --- |
| Smooth wave | Glides up and down in a steady, repeating rhythm. |
| Random drift | Wanders to random positions on its own, smoothly. Random jump is the sudden version: it holds a spot, then hops straight to a new one, so echoes and reverb seem to ping-pong around. Speed is how many hops per second. |
| Louder = higher / lower | Follows the loudness of the room. Loud sounds push the slider up (or down). |
| Upright = higher | Follows how upright the phone is. Flat on a table is lowest, standing on its end is highest. |
| Lean right = higher | Tilt the phone to the right to raise it, to the left to lower it. |
| Shake = higher | Shaking the phone pushes it up, and it settles back down after a moment. |
| Spin = higher | Turning or twirling the phone raises it. |
| Facing south = higher | Uses the compass. Facing north is lowest, facing south is highest. |
| Brighter = higher | Uses the light sensor at the top of the screen and reacts to changes in the light where you are. Covering the sensor or stepping into shade pushes it down, more light pushes it up. In steady light it settles back to the middle within a minute or two, ready for the next change. |
| In pocket = higher | Jumps up once the top of the screen has been covered and dark for about a second, such as in a pocket or lying face down, and drops back when you take the phone out. |
| Climbing = higher | Uses the air-pressure sensor. Going up stairs or in a lift raises it, going down lowers it, and standing still it sits in the middle. Not every phone has this sensor. |
| Pad X / Pad Y | Controlled by your finger on the touch pad (see below). |

For the follow-the-phone and follow-the-room choices, Speed sets how quickly the slider reacts.

**The XY pad.** With built-in effects selected, the pad on the Sound tab is a two-way control. Give one slider the movement Pad X (left to right) and another Pad Y (bottom to top), switch on movers for their sections, then drag your finger around the pad. It stays where you last touched.

Tip: a gentle Smooth wave or Random drift on a few sliders makes the sound feel alive. A mover on Echo level or Filter frequency is a good place to start.

## The Realms tab

Switch on **Auto realms** and the app listens to the room and to how you are moving, then changes the sound for you. Because a Realm sets your sliders from its own preset (effects, music, rhythm and the Mix), the app asks first; your own settings come back when the Realm ends or you switch Auto realms off. To keep part of your sound, switch that part off under the Realm's "What it changes". (Realms were called Auto worlds before; they work the same.) They only work with the built-in effects, not with scenes.

| Realm | When it plays | What it sounds like |
| --- | --- | --- |
| Tranquil | The room is quiet | Soft, dreamy, swirling sound with lots of space |
| Flux | The room is loud and lively, like voices, music or clatter (a steady roar like running water or a fan doesn't count) | Edgy and glitchy, with sounds that sometimes freeze and jump, but the room still comes through |
| Kinetic | You are walking | A pulsing sound that speeds up when you move more |
| Ghost | Midnight to 5 AM | Eerie backwards echoes and a deep, hollow room. Sudden sounds hang in the air, smeared out slowly or played backwards, and come back as rising reverse-reverb swells |
| Pocket | The phone is in a pocket or face down (covered and dark for about a second) and no other Realm fits | Quiet and muffled, with a soft room. Your drums and the music (if it is on) carry the sound. |

A Realm only starts after the situation has lasted a few seconds, so a single clap won't flip it. The sliders then glide to the new sound over about three seconds. When nothing special is going on, your own settings glide back. Stopping the app also gives them back right away. A soft, dreamy "warp" plays when a Realm starts (gliding up), when your own settings come back (gliding down), and when one Realm hands over to another (swerving sideways, from one ear to the other); you can switch it off with **Realm change sound** on the Setup tab.

There is also an **Unstable** Realm, switched off unless you pick a preset for it in the list: shake the phone hard while standing still and everything piles on at once (glitches, crushed and ring-modulated sound, a pitch shift), getting wilder the harder you shake. It comes in almost instantly and lets go about 5 seconds after you stop.

Being in a pocket doesn't stop the other Realms. In your pocket, walking still gives Kinetic, a loud and lively place still gives Flux, a quiet one Tranquil, and late night Ghost. Pocket only plays when none of them fits. Whatever Realm is playing, the pocket's own protection rides on top: Pocket hush and Mic-down protection (under Input & output).

The **Now:** line in the card names the Realm and why it was chosen, for example "Now: Kinetic · walking · ordinary room (-45 dB)": night, walking, a pocket, and how the room sounds (quiet, ordinary, loud but steady, or loud and lively). Tap **Hold realm** to keep the current Realm, for example through doorways and shops where light and noise keep changing. Tap **Let go** to release it. Stopping the sound also lets go.

**Choosing what each Realm plays.** Each Realm has a menu where you pick which preset it plays (the built-in ones are called "Tranquil realm", "Kinetic realm" and so on, and any preset you saved can be used), or turn that Realm off. Sliders you've **locked** are never changed by a Realm.

**Choosing what each Realm changes.** Under each Realm's menu, tap **What it changes** to open its switches: Rhythm, Music, Mix (the level of each part), Echo, Reverb, Glitch, Color (ring, pitch, crush, distortion, filter), Motion (chorus, flanger, phaser, tremolo), and Space and dry level. Switch a group off and that Realm leaves it at your own settings. For example, untick Reverb under Kinetic and your reverb stays exactly where you set it while you walk. The line then reads "What it changes: all but Reverb". When a Realm ends, only what it actually changed goes back, so anything you adjusted in a group it left alone stays yours.

Please tell me whether Realms change too early, too late, or not at all, and what phone and situation you were in.

## The Scenes tab

A scene is a ready-made experience from the original RjDj. While a scene is playing it replaces the built-in effects, so the Sound, Music and Realms tabs are paused. Press **Choose scene** to pick one, and **Choose scene > Built-in effects** to go back. **Import zip** and **Import folder** add scenes you already have. With a scene chosen, its touch pad shows the scene's picture, and fingers on it are sent to the scene. Scenes that show their own pictures and words on screen (for example Smile, Moogarina or Showtime, if you have them) now draw them on the pad: buttons lighting up, note names, labels.

The app includes four official example scenes made by the RjDj team (used under their open-source license):

- **Hello World World World:** a series of delays applied to the sound around you. Talk or clap and listen to it echo and pile up.
- **Onset Detection:** every sharp sound, like a clap, a tap or a beatbox pop, triggers a musical note. Quiet sounds do nothing.
- **Street Beatz:** a looping street beat plays on its own, and moving the phone changes it.
- **Vocoder:** talk or sing and your voice is turned into chords. Tilt the phone to switch between three chords.

They are older and simpler than the built-in effects, but they are the real thing. Two sliders appear for scenes: **Volume** (how loud you hear it) and **Mic volume** (how much microphone goes in). If a scene squeals, lower Mic volume. If you delete a scene by long-pressing it, it stays gone until you press Reset everything.

## Presets and shortcuts

A preset is a saved collection of slider settings, like a saved radio station. The buttons are at the top of the Sound tab.

- **Presets** opens a list of built-in presets (for example "Wobbly pitch") and the ones you saved. Tap one to load it. Long-press one you saved to delete it. Built-in ones can't be deleted.
- **Save** stores your current settings under a name you choose. Save sound, in the card at the bottom, does the same in one tap and names it after the time (like "Thu 10-31"). You can find it in Presets afterwards, or pick it for a Realm.
- **Randomize** moves every slider to a random value within a safe range. While the sound is playing it glides there over about 6 seconds, so you hear the change happen. A slider you touch during the glide stays where you put it. It's good for finding new sounds by accident. **Undo** takes you back.
- **Nudge** moves every slider only a little, so you drift to a nearby sound instead of jumping. How far it moves is set by Nudge strength in Behavior.
- **Lock** (on a slider) protects it from Randomize and Nudge, so you can keep the sounds you like and shuffle the rest.
- **Export** asks you to name the preset, then saves it as a small file. Send that file to someone, or keep it as a backup. **Import** loads a file like that. The preset appears in your list under the name it was given. If you already have one with that name, the imported one gets a number added instead of replacing yours.

The app also remembers your last settings when you close it.

## Starting fresh with Reset

On the Setup tab is a **Reset everything to defaults** button. It asks you to confirm, then puts every slider, mover, lock, Realm setting and audio choice back to how the app was when you first installed it, so you can experiment without leftovers from earlier tries. It keeps your saved presets, any scenes you imported, and your appearance choice. If you deleted one of the four built-in scenes, Reset brings it back. Nothing is ever reset unless you press this button and confirm. Because updating the app keeps your old settings, Reset is also how you get the newest starting values after an update.

If you ever uninstall the app, everything in it is erased, including your saved presets. To keep your favorites, use Presets > Export on each one first and Import them again afterward.

A preset file holds the effect sliders, their movers, the Music and Rhythm levels, Chime character, and the Dry level. It does not hold: Input gain, noise gate and compressor (and their shape); Pocket hush, Mic-down protection and Handling hush; Intensity; Smoothing and Nudge strength; whether Music is switched on, its key and scale, Pad register, the home-chord drift and "Light, pocket and stairs move the notes" switches, Calm builds, and the Synth / Found sounds choices; the Rhythm's tempo settings and "Beat follows" and "Beat plays"; the Realm change sound; locks; the Realm choices; the stem pack choice; your audio device choices; imported scenes and packs; or the appearance look. Set those again by hand after reinstalling.

## The Setup tab

- **Audio devices** has Input (microphone) and Output menus. Output is always headphones or earbuds, wired or Bluetooth. The app picks wired first, then Bluetooth, and you can choose another pair from the menu. For Input you can pick the phone's own mic, a wired headset mic, or a Bluetooth headset mic. Careful with that last one: most Bluetooth earbuds can only use their mic in "phone call mode", which sounds thin and low quality. For the best sound, choose the phone's mic or a wired headset. Some newer headsets (Bluetooth LE Audio) do better, and the app shows a hint under the Input menu about the one you picked. Wired headphones also have the least delay.
- **Appearance** switches between a light look, a dark look (the default) and a pure-black look that suits OLED screens.
- **About and licenses** shows the open-source licenses and where to send feedback, and can show the welcome pages again. **Send feedback** writes an email to Dad for you: your phone model, Android and app versions are filled in, and if you leave the box ticked, the app's recent event log is added (no sound and nothing you said: just times, the room's loudness as numbers, and what the app did). You can read and change everything before sending. The app is free software and includes parts of the original RjDj project.

- **Diagnostics** (tap to open) shows, while the sound runs: the mic Android is really using (handy with Input on Automatic), whether a Bluetooth mic is in thin call mode, the headphones being played to, the mic level after Input gain (with the noise gate's setting next to it, so you can see whether the room is above or below it), and overloads in the last minute. **Mic overloads** mean the sound was too loud or too close for the mic itself, which sounds harsh; Input gain can't fix that, because the overload happens before it. **Output limiter squashing hard** means the mix is too hot: if it sounds harsh, lower Input gain or some effect levels. It also counts **handling noises skipped**: taps and grips on the phone that weren't caught as found sounds. One loud clap may count once; that's fine. When the mic keeps overloading, the status line at the bottom says "Mic overloading" on every tab until it stops. Please mention these numbers when you report a harsh or distorted sound.
- **Behavior:** **Smoothing** sets how smoothly the sound glides when you change a slider (low gives instant, snappy changes, high gives slow slides). **Nudge strength** sets how far the Nudge button moves things. **Realm change sound** switches the warp sound off or on.
- **Reset everything to defaults** (see "Starting fresh with Reset").

**Earbud and headset mics are much quieter than the phone's.** They are made for your voice right next to them, not for hearing a room, so a USB-C, wired or Bluetooth headset mic can sound silent at first. If you pick one as Input, open **Input & output**, raise **Input gain** (around 8 worked for USB-C earbuds, against 2.5 for the phone mic) and lower **Noise gate threshold**, all the way to -80 if needed (-80 switches the gate off). When you go back to the phone's mic, turn them back, or it will be loud and hissy. The app keeps one set of these settings for every mic, because Android gives many headsets the same generic name and the app can't tell them apart.

**Phone calls and other apps.** When a call rings or starts, including calls in apps like WhatsApp, the app goes silent and says so. It plays again by itself when the call ends. When another app plays sound, like music or navigation, the app turns itself down a little (about 3 dB) so you can hear both, and comes back up when the other sound stops. It never pauses your music app. This works on Android 12 and newer.

## What to test and how to send feedback

Thank you for trying this. Anything you notice is useful, even "it felt weird." Things I especially want to know:

- **Your phone and Android version.** For example, "Pixel 8, Android 15."
- **Sound problems:** crackling, dropouts, silence, a squeal, or delay between making a sound and hearing it. Say which effects were on. Crackling or stuttering with many things switched on can mean your phone is working too hard; tell me which ones.
- **Does it keep running** when you lock the screen or switch to another app?
- **Battery and heat:** does your phone get warm, or does the battery drain fast?
- **Anything confusing** on screen, such as a label or button you didn't understand. Is the card at the bottom easy to reach while walking, are the tabs easy to tap, and does the Now: line make sense? Is everything on the tab you expected?
- **Crashes or freezes:** what you were doing just before.
- **Call and response:** does the answer come at a natural moment after you stop singing, and does it sound like your phrase?
- **Movers:** do the tilt, shake, spin, compass, light, pocket and stairs movements feel right? Does a sensor seem to be missing on your phone?
- **Intensity:** try both ends while you walk. Is the left end calm without going dead, and the right end busy without turning into a mess? Is the middle the sound you set up?
- **Scenes with pictures:** if you have scenes that draw on screen (Smile, Moogarina, MoonBootSynthPad, Showtime, TouchVocoder, Atsuke), do their pictures and words appear in the right places and change as you play?
- **Calm builds:** switch it on and stand somewhere calm for five minutes or so. Does the build feel gradual and natural? Is the top too much or too little? Does it get out of the way quickly when you start walking?
- **Handling:** tap, grip and rub the phone while it plays. Are those sounds quieter, and do they stay out of the beat and the chimes (Diagnostics counts the skipped ones)? Walk holding the phone: does the found-sound beat still pick up the sounds around you? Clap and knock nearby with the phone still: are those still caught?
- **Pocket:** with the phone in a pocket, both mic end up and mic end down, how much cloth noise do you hear? Can you still hear the world around you? Which Pocket hush and Mic-down protection settings worked for you?
- **Presets:** does Export then Import bring back the same sound?
- **Favorites:** which effects or presets did you enjoy, and which did you ignore?
- **Music:** does it stay quiet in a quiet room, answer when something happens, and swell as you walk faster? Is the pad too loud, or the notes too busy? Do the chimes fall in time with the beat?
- **Found sounds:** do the drums, chimes and room notes sound like the sounds around you? Is the beat too predictable, or too random? Where on the Chime character slider do you like the chimes? Does anything loud or harsh come back from the kit (a boom, a squeal)?
- **Harmony:** does your voice copy sound like you and stay in tune? Does it sound natural when you sing low and when you sing high? Does it leave ordinary talking alone?
- **Found pad:** after you hum a steady note, does the pad sound like your voice holding the chord?
- **Rhythm:** does the beat stay steady while you walk and follow a change of pace? With Tempo set to Set, does it settle on your tempo, and does walking pull it the right amount? Do the occasional sparse bars and the drifting swing feel musical? With Melody rhythm on, do the walking notes and chimes feel like they have a rhythm, and do long and short notes sound right? With Melody phrases on, can you hear the line repeat and come back? With Breakbeat up, do the chops, rolls and fills feel like a breakbeat, and is the top of the slider too much or not enough? Does the beat still land on your steps as you walk?
- **Realms:** do they change at the right moments? Do the "What it changes" switches leave the groups you untick alone? Is the warp sound pleasant, and noticeable without being annoying?
- **Glitch:** with Glitch cloud amount up, do sudden sounds come back in a fun way, and do they feel like they are all around you? Which glitch matrix mix did you like best? Do the echoes bouncing around (Echo scatter) feel good or dizzying?
- **Headphones and mic:** did the app refuse to start, stop when you unplugged, or pick the wrong mic? Did it go quiet during a call and come back after, and did it dip when another app played music?
- **Scenes:** does each of the four built-in scenes make sound, and does it react the way its description says? Tell me which ones felt dead, too loud or confusing.

The easiest way: **Setup > About and licenses > Send feedback**, which fills in your phone and app details for you. Or send feedback to DadCraft on Discord, or email it to dadcraftstudios@gmail.com. Screenshots help, and so does a short description of the steps that led to a problem.

Please use headphones, keep the volume low at first, and take a break if the sound is intense. The app can get loud.
