# Licensing and third-party notices

PdScenes is free software, released under the **GNU General Public License v3.0 or later**
(see `LICENSE`). You may use, study, change and share it under those terms.

It bundles and depends on the following. Full texts are in `app/src/main/assets/licenses/` and are shown
inside the app under *About and licenses*.

| Component | Licence | Where |
|---|---|---|
| RjDj library of Pd abstractions (`rjlib`), by Reality Jockey Ltd. | GPLv3; a few files (ADSR, vocoder) are Standard Improved BSD | `assets/scene_lib/rj/`, and the legacy helpers (`reverb`, `sssad`, `rjdispatch`, `rjloader`, `accelerate`, `touch`, ...) beside it |
| Pure Data extras (`hilbert~`, `rev1~`..`rev3~`, `complex-mod~`) by Miller Puckette and others | Standard Improved BSD | `assets/scene_lib/` |
| The four official RjDj example scenes (`HelloWorldWorldWorld.rj` by Frank Barknecht; `OnsetDetection.rj`, `StreetBeatz.rj`, `Vocoder.rj` by the RjDj team), from `rjdj/rjlib` `examplescenes/` | GPLv3 (each scene folder carries its `LICENSE.txt`; the Pd patches say "GNU General Public License ver. 3 or later") | `assets/builtin_scenes/` |
| Helper abstractions `closebang`, `rj_compass`, `rj_loc`, `rj_text`, `rj_time`, `rjdj` (and `rj_image`), from PdParty by Dan Wilcox, Copyright 2011-2023 | Simplified BSD (`assets/licenses/pdparty-LICENSE.txt`) | `assets/scene_lib/` |
| libpd / pd-for-android (`pd-core`) | Standard Improved BSD | Gradle dependency |
| Oboe (audio backend inside `pd-core`) | Apache License 2.0 | Gradle dependency |

`soundinput.pd` and `soundoutput.pd` in `assets/scene_lib/` were written for this app.

The four scenes above are the only scenes bundled. RjDj scenes that you import yourself are not part of this app and keep
their own authors' licences. The bundled scenes keep only the abstractions that differ from the shared library in `assets/scene_lib/rj/`;
the rest of their original `rj/` folders are identical copies of it and were left out to save space. One shared file,
`s_fplaytable.pd`, has a small fix (see the note inside it) so that sample-playing scenes work with current Pure Data.

"RjDj" is a name used by its original authors; this project is not affiliated with or endorsed by them.
