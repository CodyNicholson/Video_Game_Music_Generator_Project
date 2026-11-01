---
name: chiptune-composer
description: Compose original chiptune game music and render it to seamless looping WAV, stems and MIDI using a self-written local synth, with no AI music service, samples, royalties or usage limits. The house style is orchestral-big-band adventure in chip form, inspired by Dreamcast-era JRPG soundtracks like Skies of Arcadia. Use this whenever the user wants game music, a soundtrack, a level or battle or town or overworld theme, a victory jingle, a looping track, adaptive music layers, 8-bit or 16-bit or retro or FM audio, or wants to change or re-render a song made with this skill, even if they don't say "chiptune".
---

# Chiptune Composer

Write a song as a JSON score, then render it with the bundled synth. Every sound is computed locally from math, so the result has no sample libraries, service terms or revenue limits attached.

## Setup

Run commands from the project root. The renderer needs Python 3 and NumPy. If `.venv` is missing:

```bash
python3 -m venv .venv && .venv/bin/pip install numpy
```

Below, `SKILL` is `.claude/skills/chiptune-composer`.

## Workflow

1. **Pin down the brief.** Get the game moment, mood, length and whether it loops. Default to a loop of 30 to 90 seconds with a short intro. Only ask when the answer would change the piece a lot, since a wrong guess is cheap to re-render.
2. **Read the references.** Read `references/style-guide.md` for how to write in this style, and `references/song-format.md` for the score format and instrument list. Open a file in `assets/examples/` that is close to the brief to see the format in real use.
3. **Compose in this order:** chords, then melody, then bass, then countermelody and pads, then drums, then stabs and fills. Melody quality decides whether the piece works, so draft it first, and sing through its rhythm and contour before orchestrating.
4. **Save the score** to `music/<name>.json` in the project and fill in `chords` for every section, because the checker uses them to find wrong notes.
5. **Check it:**
   ```bash
   .venv/bin/python SKILL/scripts/render.py music/<name>.json --check
   ```
   Fix every error. Treat each warning as a question: a chromatic passing note can be right, but an unplanned clash is a bug.
6. **Render it:**
   ```bash
   .venv/bin/python SKILL/scripts/render.py music/<name>.json --out output --preview
   ```
   Use `--section NAME` to audition one section quickly.
7. **Review the numbers.** You can't hear the audio, so use the printed report and the spectrogram PNG (see "Reading the report"), and fix anything out of line.
8. **Report back.** Give the file paths, the piece's structure and the loop points, then ask the user to listen. Say clearly that you verified the audio by measurement and not by ear, because only they can judge whether it sounds good. Offer `afplay <file>` on macOS.

## Writing original music

Work from a style, never from a specific tune. When a user names a game or composer, take the instrumentation, harmony, energy and form from it, and write new melodies. Decline to transcribe or closely paraphrase an existing theme, even with small changes, because that is what would create a real copyright problem for the user's game. For the same reason, tell users their own edits to the melody or the MIDI strengthen their authorship claim.

## Files produced

Everything goes in `<out>/<name>/`:

| File | Use |
|---|---|
| `<name>.wav` | Full mix with all layers. Its `smpl` chunk holds the loop points. |
| `<name>_stem_<layer>.wav` | One file per layer, only when the song has more than one. Same length; they sum to the mix. |
| `<name>_loop_preview.wav` | Plays the intro and then the loop twice, to audition the seam. Not for the game. |
| `<name>.mid` | Editable arrangement for any DAW. It carries notes and tempo, not the synth's sound. |
| `<name>.json` | Loop samples, section times and the analysis report. |
| `<name>_spectrogram.png` | Picture of the audio over time. |

Same score in, identical audio out, so the JSON score is the source of truth: keep it in version control and treat the WAVs as build output.

## Using it in a game

- **Looping:** start playback at sample 0 and, on reaching `loop_end_sample`, jump to `loop_start_sample`. These are in `<name>.json`.
- **Adaptive music:** play all stems in sync and fade layers in and out. The stems are sample-aligned so this stays in time.
- **File format:** the renderer writes WAV. Convert to OGG for shipping with whatever tool the project uses, and check the engine keeps the loop points, since many converters drop them.

## Reading the report

Use these as rough guides for spotting problems, not as targets:

- **Peak** should be -1 dBFS with 0 clipped samples. The renderer normalizes to this automatically.
- **Voice RMS:** the lead should be among the loudest non-bass voices. If it sits more than about 6 dB below the accompaniment, raise its `gain` or thin the parts around it. Voices that rest a lot read low, and that is fine.
- **Band balance:** for a full arrangement, bass and mid should be the top bands, and presence and air should fall away from them. If sub is the top band, the mix is boomy. If presence is within a few dB of mid, it will likely be harsh.
- **Section RMS** should change with the form. If a chorus isn't louder or denser than its verse, the arrangement isn't building.
- **Loop seam:** `seam ok: False` means something is wrong in the renderer, so don't ship it. Report it as a bug.
- **Spectrogram:** look for sections that differ from each other, silent gaps you didn't write, and unbroken bright bands that suggest a note stuck on or a voice too loud.

## Limits worth telling the user

This renders chip and FM-style sound, not realistic orchestra or vocals. Lyrics, sung parts and recordings of real instruments aren't possible. It also has no realtime component, so adaptive behaviour comes from the game engine crossfading stems.

## Tests

```bash
.venv/bin/python -m unittest discover -s SKILL/tests
```

Run these after changing anything in `scripts/`.
