# Song format

A song is one JSON file. See `assets/examples/` for complete pieces.

## Contents

- Top level
- Voices
- Sections
- Note notation
- Instruments
- Drums
- Layers and loops

## Top level

```json
{
  "title": "Skyward Regatta",
  "bpm": 138,
  "meter": "4/4",
  "key": "D major",
  "swing": 0,
  "loop": true,
  "loop_from": 1,
  "voices": {},
  "sections": {},
  "arrangement": ["intro", "soar", {"section": "soar", "transpose": 2}]
}
```

- `bpm` is always quarter notes per minute, including in 6/8.
- `loop_from` is the arrangement index where the loop begins. Entries before it are the intro and play once. Defaults to 0.
- `loop: false` makes a one-shot such as a jingle, and keeps the ringing tail.
- `swing` is where the off-beat eighth lands within the beat. Use 0 for straight, or 0.58 to 0.66 for swung. Avoid it in 6/8, and don't combine it with written triplets in the same voice, since they would be pulled off their grid.
- `key` accepts major, minor, dorian, phrygian, lydian, mixolydian, aeolian, ionian and locrian. It's used only for checking.

## Voices

```json
"lead": {"instrument": "trumpet", "gain": 1.0, "pan": -0.2, "reverb": 0.2, "echo": 0.2,
         "layer": "base", "octave": 0, "arp": 0.25, "swing": true, "params": {"duty": 0.25}}
```

Only `instrument` is required.

- `gain` is a volume multiplier, and `pan` runs from -1 (left) to 1 (right).
- `reverb` overrides the instrument's send amount.
- `echo` adds a dotted-eighth ping-pong delay. 0.15 to 0.3 is a good range.
- `layer` names the stem the voice belongs to.
- `octave` shifts the whole voice by octaves.
- `arp` turns chords into fast arpeggios, with this many beats per step. 0.25 is sixteenths.
- `swing: false` keeps the voice straight in a swung song.
- `params` overrides any instrument setting; see `_BASE` in `scripts/synth.py` for names. Typos are rejected.

## Sections

```json
"soar": {
  "bars": 8,
  "chords": "D | A/C# | Bm | G | D | G | Em7 A7 | D",
  "key": "D major",
  "bpm": 138, "swing": 0, "meter": "4/4",
  "parts": {"lead": "F#5:1! A5:1/2 F#5:1/2 D5:2 | ..."}
}
```

`bars` and `parts` are required. A voice left out of `parts` is silent for that section. `bpm`, `swing`, `meter` and `key` override the song's values for this section.

`chords` has one `|`-separated group per bar, and chords in a bar split it evenly. They produce no sound and exist so the checker can find wrong notes. Qualities: (none), maj, m, min, 5, 6, m6, 7, maj7, m7, 9, m9, maj9, add9, sus2, sus4, 7sus4, dim, dim7, m7b5, aug. Slash basses such as `A/C#` work.

Arrangement entries are section names or `{"section": "soar", "transpose": 2}`. Transposing doesn't move drums, so one section can serve a key-change lift.

## Note notation

Tokens are separated by spaces, written as `PITCH:DURATION` plus optional marks.

| Write | Meaning |
|---|---|
| `D5:1` | D in octave 5 for one quarter note (middle C is C4) |
| `F#4:1/2`, `Bb3:3/2` | Sharps and flats; durations can be fractions |
| `C5:1/3` | Triplet. Write fractions: `0.33` won't add up and is rejected |
| `r:2` | Rest |
| `D4+F#4+A4:4` | Chord, or simultaneous drums like `kick+hat:1/2` |
| `\|` | Barline. Every bar is checked to add up exactly, so use them |
| `@0.7` | Velocity from here on, 0 to 1. Default 0.8 |
| `{ ... }*4` | Repeat. Groups can nest; keep a barline inside: `{ ... \|}*4` |

Durations are in quarter notes in every meter, so a 6/8 bar totals 3 and a dotted quarter is `3/2`.

Marks go after the duration:

| Mark | Effect |
|---|---|
| `!` | Accent: louder, and brighter on FM brass |
| `.` | Staccato: half length |
| `-` | Tenuto: full length |
| `^` | Scoop up into the note, a big-band gesture |
| `v` | Fall off at the end, a big-band gesture |
| `~` | Twice the vibrato |
| `&` | Tie into the next note, which must have the same pitch. Works across barlines |

Example: `D5:0.5.` is a staccato eighth, and `G5:3~` is a dotted half with wide vibrato.

## Instruments

| Family | Names |
|---|---|
| Brass (FM) | `trumpet`, `trumpet_section`, `horn`, `trombone`, `tuba` |
| Choir-like pad | `choir_pad` (a wordless synth pad, not vocals) |
| Reeds (FM) | `sax` |
| Strings | `strings` (sustained), `strings_lead` (soaring melody), `strings_ostinato` (fast figures), `strings_stab`, `strings_chip` (pulse), `low_strings`, `pizz` |
| Woodwinds and folk | `flute`, `clarinet`, `oboe`, `whistle`, `accordion`, `guitar`, `harp`, `bell` |
| Chip | `pulse_lead`, `square`, `arp` |
| Bass and low | `bass`, `upright`, `timpani` |

The checker warns when notes fall outside an instrument's range, listed in `scripts/synth.py`.

## Drums

Set `"instrument": "drums"`. Names: `kick`, `snare`, `rim`, `clap`, `hat`, `ohat`, `ride`, `crash`, `tom_hi`, `tom_lo`, `shaker`, `tamb`, `brush`, `bdrum` (concert bass drum), `gong`, `swell`. `swell` is a cymbal roll that grows over its written duration; the others ignore duration.

## Layers and loops

Voices with the same `layer` render into one stem. All voices default to `base`. For adaptive music, put the always-on arrangement in `base` and the extras in named layers such as `storm`, and write the extras so the piece works with or without them.

Loops wrap automatically: release tails and reverb that run past the end are folded back to the loop start, so the seam is continuous. Write the last bar of the loop to lead back into its first bar harmonically, typically by ending on the dominant. An intro's ringing tail is cut at the loop start, so land the loop's first bar on a strong downbeat to cover it.
