#!/usr/bin/env python3
"""Writes the beat-synced deck battle scores to music/*.json. The melodies are written out by hand below,
and this file fills in the repeating accompaniment. Edit here and re-run it, then render the JSON with the
chiptune-composer skill.

Every song in this set shares one clock, because the game times its deck battle turns to the music:

  * 160 BPM, straight 4/4. One beat is 0.375 s, and two bars, the "beat sequence", are exactly 3 s.
  * The pulse is the same in every section of every song, and section() writes it in, so no section can
    drop it: a kick on every beat and a snare and clap backbeat; on each sequence's first beat an
    orchestra hit (brass and string stab, crash, taiko, timpani); a cymbal swell over beats 7 and 8 and a
    snare roll on beat 8 into the next one. The player hears a turn coming before it starts.
  * Every section is a whole number of sequences, so the intro and the loop are too, and the
    sequence grid survives the loop seam.
"""

import json
import re
from pathlib import Path

from build_dogfight_scores import (QUALITY, bars_of, danger_parts, drive_332, gallop, held_bass, join, name,
                                   offbeat_stabs, pad, root, runs, stabs_332, tones, tremolo, voice)

HERE = Path(__file__).resolve().parent
QUALITY.setdefault("maj7", (0, 4, 7, 11))

BPM = 160
SEQUENCE_BARS = 2

# The shared beat sequence, as two bars of drums. Every style keeps a kick on every beat, the backbeat,
# the crash on beat 1 and the snare roll on beat 8. Only the cymbal colour and the snare's ghost notes differ.
CYCLE = {
    "full": ("crash+kick+bdrum:1/2! hat:1/2 kick+snare+clap:1/2! hat:1/2 kick:1/2 ohat:1/2 kick+snare+clap:1/2! hat:1/2",
             "kick:1/2 hat:1/2 kick+snare+clap:1/2! hat:1/2 kick:1/2 ohat:1/2 snare:1/4 snare:1/4 snare:1/4 snare:1/4"),
    "march": ("crash+kick+bdrum:1/2! field_snare:1/4 field_snare:1/4 kick+field_snare+clap:1/2! field_snare:1/2 kick:1/2 field_snare:1/4 field_snare:1/4 kick+field_snare+clap:1/2! field_snare:1/2",
              "kick:1/2 field_snare:1/4 field_snare:1/4 kick+field_snare+clap:1/2! field_snare:1/2 kick:1/2 field_snare:1/4 field_snare:1/4 snare:1/4 snare:1/4 snare:1/4 snare:1/4"),
    "lift": ("crash+kick+bdrum:1/2! ride:1/2 kick+snare+clap:1/2! ride:1/2 kick:1/2 ride:1/2 kick+snare+clap:1/2! ride:1/2",
             "kick:1/2 ride:1/2 kick+snare+clap:1/2! ride:1/2 kick:1/2 ride:1/2 snare:1/4 snare:1/4 snare:1/4 snare:1/4"),
}
WAR = ("taiko+bdrum:1! r:1 taiko_hi:1/2 taiko_hi:1/2 r:1", "r:1 taiko_hi:1/2 taiko_hi:1/2 r:1 taiko_hi:1/4 taiko_hi:1/4 taiko:1/2!")
RISER = ("r:4", "r:2 swell:2")

# The pulse's voices, the same in every song. Loud on purpose: the beat is what the player plays to.
PULSE_VOICES = {
    "perc": voice("drums", 1.05),
    "war": voice("drums", 0.85, 0.0),
    "riser": voice("drums", 2.4, 0.0),
    "timp": voice("timpani", 0.7, -0.08),
    "hit": voice("strings_stab", 2.2, -0.12),
    "hit_brass": voice("trumpet_section", 1.0, 0.12),
}


def octave(text, shift):
    """Moves every pitch in a part by whole octaves."""
    return re.sub(r"([A-G][#b]?)(\d)(?=[:+])", lambda m: f"{m.group(1)}{int(m.group(2)) + shift}", text)


def sequences(bars):
    if bars % SEQUENCE_BARS:
        raise ValueError(f"A section of {bars} bars would break the three-second sequence")
    return bars // SEQUENCE_BARS


def cycle_drums(bars, style="full"):
    return join(list(CYCLE[style]) * sequences(bars))


def cycle_war(bars):
    return join(list(WAR) * sequences(bars))


def cycle_timp(chords):
    """The timpani marks each sequence: the root on its first beat, a roll into the next one on its last."""
    bars = bars_of(chords)
    sequences(len(bars))
    out = []
    for i in range(0, len(bars), SEQUENCE_BARS):
        first = name(root(bars[i][0], 41))
        last = name(root(bars[i + 1][-1], 41))
        out += [f"{first}:1! r:3", f"r:3 {last}:1/4 {last}:1/4 {last}:1/4 {last}:1/4"]
    return join(out)


def cycle_riser(bars):
    return join(list(RISER) * sequences(bars))


def cycle_hits(chords, low):
    """A short, accented full chord on each sequence's first beat: the orchestra hit."""
    bars = bars_of(chords)
    out = []
    for i in range(0, len(bars), SEQUENCE_BARS):
        chord = "+".join(name(p) for p in tones(bars[i][0], low)[:3])
        out += [f"{chord}:1/2! r:7/2", "r:4"]
    return join(out)


def section(bars, chords, parts, **extra):
    """Writes the shared pulse over whatever the section had, so every section keeps the same beat.
    A section that wrote a march (field snare) keeps that colour, and a gentle one keeps the ride."""
    sequences(bars)
    if len(bars_of(chords)) != bars:
        raise ValueError(f"{bars} bars but {len(bars_of(chords))} bars of chords")
    written = parts.get("perc", "")
    style = "march" if "field_snare" in written else "lift" if "ride:" in written else "full"
    parts = dict(parts)
    parts["perc"] = "@0.95 " + cycle_drums(bars, style)
    parts["war"] = "@0.9 " + cycle_war(bars)
    parts["riser"] = "@0.8 " + cycle_riser(bars)
    parts["timp"] = "@0.95 " + cycle_timp(chords)
    parts["hit"] = "@1.0 " + cycle_hits(chords, 55)
    parts["hit_brass"] = "@1.0 " + cycle_hits(chords, 62)
    return {"bars": bars, "chords": chords, "parts": parts, **extra}


def song(title, key, voices, sections, arrangement):
    total = sum(sections[entry if isinstance(entry, str) else entry["section"]]["bars"] for entry in arrangement)
    sequences(total)
    return {"title": title, "bpm": BPM, "meter": "4/4", "key": key, "swing": 0, "loop": True, "loop_from": 1,
            "voices": {**voices, **PULSE_VOICES}, "sections": sections, "arrangement": arrangement}


ORCH_DANGER = {
    "x_tremolo": voice("orch_tremolo", 1.8, -0.36, layer="danger"),
    "x_bones": voice("orch_trombones", 0.72, 0.36, layer="danger"),
    "x_war": voice("drums", 0.62, 0.15, layer="danger"),
}


# ---- Song one: Boarding Cadence. D minor, orchestral, the everyday deck brawl. ----

def boarding_cadence():
    voices = {
        "trumpets": voice("orch_trumpets", 1.4, 0.12),
        "horns": voice("orch_horns", 1.05, -0.32),
        "bones": voice("orch_trombones", 1.0, 0.24),
        "tuba": voice("orch_tuba", 0.8, -0.04),
        "violins": voice("orch_violins", 1.9, -0.16),
        "spiccato": voice("orch_spiccato", 1.2, 0.3),
        "celli": voice("orch_celli", 0.85, -0.24),
        "basses": voice("orch_basses", 0.75, 0.0),
        "strings": voice("orch_strings", 0.95, 0.0),
        "choir": voice("orch_choir", 0.9, 0.0),
        "winds": voice("orch_winds", 0.8, 0.38),
        "timp": voice("timpani", 0.4, -0.08),
        "perc": voice("drums", 0.62),
        "war": voice("drums", 0.5),
        **ORCH_DANGER,
    }

    muster = section(2, "Dm | A7", {
        "trumpets": "@0.9 D5+F5+A5:1! r:3 | C#5+E5+A5:1! r:1 C#5+E5+G5:1/2! C#5+E5+G5:1/2 C#5+E5+G5:1/2 C#5+E5+G5:1/2",
        "bones": "@0.85 D2+A2:1! r:3 | A2+E3:1! r:3",
        "tuba": "@0.85 D1:4 | A1:4",
        "strings": "@0.6 D3+F3+A3:4 | C#3+E3+G3:4",
        "timp": "@0.9 " + cycle_timp("Dm | A7"),
        "perc": "@0.8 " + cycle_drums(2),
        "war": "@0.75 " + cycle_war(2),
    })

    riff_chords = "Dm | Dm | Bb | A | Dm | Dm | Gm Bb | A7"
    riff = ("D3:3/4! D3:3/4 F3:1/2! r:1/2 A3:1/2 G3:1/2 F3:1/2 | "
            "E3:3/4! D3:3/4 A2:1/2! r:1/2 C3:1/2 D3:1/2 E3:1/2 | "
            "Bb2:3/4! Bb2:3/4 D3:1/2! r:1/2 F3:1/2 E3:1/2 D3:1/2 | "
            "C#3:3/4! E3:3/4 A3:1/2! r:1/2 G3:1/2 E3:1/2 C#3:1/2 | "
            "D3:3/4! D3:3/4 F3:1/2! r:1/2 A3:1/2 G3:1/2 F3:1/2 | "
            "F3:3/4! E3:3/4 D3:1/2! r:1/2 A3:1/2 Bb3:1/2 A3:1/2 | "
            "G3:3/4! Bb3:3/4 D3:1/2! Bb2:3/4! D3:3/4 F3:1/2! | "
            "A2:3/4! C#3:3/4 E3:1/2! G3:1 A3:1!")
    bars = bars_of(riff_chords)
    riff_section = section(8, riff_chords, {
        "bones": "@0.9 " + riff,
        "horns": "@0.7 " + octave(riff, 1),
        "spiccato": "@0.66 " + join(gallop(bar) for bar in bars),
        "celli": "@0.75 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.75 " + join(drive_332(bar, 26) for bar in bars),
        "tuba": "@0.62 " + join(held_bass(bar, 26) for bar in bars),
        "strings": "@0.42 " + join(pad(bar) for bar in bars),
        "timp": "@0.8 " + cycle_timp(riff_chords),
        "perc": "@0.6 " + cycle_drums(8),
        "war": "@0.72 " + cycle_war(8),
        **danger_parts(riff_chords),
    })

    theme_chords = "Dm | Bb | F | C | Dm | Bb | Gm A7 | Dm A7"
    bars = bars_of(theme_chords)
    theme = section(8, theme_chords, {
        "trumpets": "@0.95 A4:1! D5:1 F5:3/2 E5:1/2 | D5:1 Bb4:1/2 D5:1/2 F5:2~ | C5:1! F5:1 A5:3/2 G5:1/2 | G5:3~ E5:1/2 C5:1/2 | "
                    "A4:1! D5:1 F5:1 A5:1 | Bb5:3/2! A5:1/2 F5:1 D5:1 | D5:1 G5:1 E5:1 C#5:1 | D5:2~ r:1 A4:1",
        "horns": "@0.8 F4:2 A4:2 | F4:2 D4:2 | A4:2 C5:2 | G4:2 E4:2 | F4:2 A4:2 | F4:2 D4:2 | Bb4:2 A4:2 | A4:2 G4:2",
        "bones": "@0.78 " + join(offbeat_stabs(bar, 48) for bar in bars),
        "spiccato": "@0.64 " + join(runs(bar) for bar in bars),
        "celli": "@0.78 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.78 " + join(drive_332(bar, 26) for bar in bars),
        "tuba": "@0.7 " + join(held_bass(bar, 26) for bar in bars),
        "strings": "@0.5 " + join(pad(bar) for bar in bars),
        "timp": "@0.85 " + cycle_timp(theme_chords),
        "perc": "@0.68 " + cycle_drums(8),
        "war": "@0.68 " + cycle_war(8),
        **danger_parts(theme_chords),
    })

    stalk_chords = "Gm | Gm | Eb | D | Gm | Gm | Em7b5 | A7"
    bars = bars_of(stalk_chords)
    stalk = section(8, stalk_chords, {
        "horns": "@0.9 G3:3/2! Bb3:1/2 D4:2 | D4:1 C4:1/2 Bb3:1/2 G3:2 | Eb4:3/2! G4:1/2 Bb4:2 | A4:1 F#4:1 D4:2 | "
                 "G4:3/2! Bb4:1/2 D5:2~ | C5:1 Bb4:1/2 A4:1/2 G4:2 | G4:1 Bb4:1 E4:2 | C#4:1 E4:1 A4:2-",
        "winds": "@0.66 r:2 G5:1/4 Bb5:1/4 D6:1/4 G6:1/4 Bb6:1 | r:4 | r:2 Eb5:1/4 G5:1/4 Bb5:1/4 Eb6:1/4 G6:1 | r:4 | "
                 "r:2 G5:1/4 Bb5:1/4 D6:1/4 G6:1/4 Bb6:1 | r:4 | r:2 E5:1/4 G5:1/4 Bb5:1/4 E6:1/4 G6:1 | "
                 "A5:1/4 C#6:1/4 E6:1/4 G6:1/4 A6:1/4 G6:1/4 E6:1/4 C#6:1/4 A5:2",
        "spiccato": "@0.6 " + join(gallop(bar) for bar in bars),
        "celli": "@0.66 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.68 " + join(held_bass(bar, 26) for bar in bars),
        "strings": "@0.46 " + join(pad(bar) for bar in bars),
        "timp": "@0.75 " + cycle_timp(stalk_chords),
        "perc": "@0.5 " + cycle_drums(8, "march"),
        **danger_parts(stalk_chords, war=False),
    })

    valor_chords = "F | C/E | Dm | Bb | Gm | C | F Bb | C"
    bars = bars_of(valor_chords)
    valor = section(8, valor_chords, {
        "violins": "@0.88 C5:1/2! F5:1/2 A5:1 C6:3/2 A5:1/2 | G5:2~ E5:1 C5:1 | D5:1/2! F5:1/2 A5:1 D6:3/2 C6:1/2 | Bb5:2~ F5:1 D5:1 | "
                   "G5:1! Bb5:1 D6:1 C6:1/2 Bb5:1/2 | C6:3/2 G5:1/2 E5:2 | F5:1 A5:1 Bb5:1 D6:1 | E6:2~ D6:1 C6:1",
        "horns": "@0.62 A3:2 C4:2 | G3:2 C4:2 | F3:2 A3:2 | F3:2 D4:2 | G3:2 Bb3:2 | G3:2 E4:2 | A3:2 Bb3:2 | G3:2 E4:2",
        "strings": "@0.58 " + join(pad(bar) for bar in bars),
        "choir": "@0.56 " + join(pad(bar, 60) for bar in bars),
        "celli": "@0.62 " + join(held_bass(bar, 36) for bar in bars),
        "basses": "@0.62 " + join(held_bass(bar, 26) for bar in bars),
        "timp": "@0.55 " + cycle_timp(valor_chords),
        "perc": "@0.55 " + cycle_drums(8, "lift"),
        "x_tremolo": "@0.36 " + join(tremolo(bar) for bar in bars),
    }, key="F major")

    turn_chords = "Bb | C | A7 | A7"
    bars = bars_of(turn_chords)
    turn = section(4, turn_chords, {
        "trumpets": "@0.95 D5+F5+Bb5:1/2! r:1/2 D5+F5+Bb5:1/2! r:1/2 D5+F5+Bb5:2- | E5+G5+C6:1/2! r:1/2 E5+G5+C6:1/2! r:1/2 E5+G5+C6:2- | "
                    "C#5+E5+A5:1/2! r:1/2 C#5+E5+A5:1/2! r:1/2 E5+G5+C#6:1/2! r:1/2 E5+G5+C#6:1/2! r:1/2 | C#5+G5+A5:1! r:1 C#5+E5+A5:2-",
        "horns": "@0.85 Bb3+F4:4 | C4+G4:4 | A3+E4:4 | A3+G4:4",
        "bones": "@0.9 Bb2:1! Bb2:1 Bb2:1 D3:1 | C3:1! C3:1 E3:1 G3:1 | A2:1! C#3:1 E3:1 G3:1 | A3:1! G3:1/2 E3:1/2 C#3:1 A2:1!",
        "spiccato": "@0.7 " + join(runs(bar) for bar in bars),
        "tuba": "@0.8 Bb1:4 | C2:4 | A1:4 | A1:4",
        "basses": "@0.8 " + join(drive_332(bar, 26) for bar in bars),
        "strings": "@0.62 Bb3+D4+F4:4 | C4+E4+G4:4 | A3+C#4+E4:4 | A3+C#4+G4:4",
        "choir": "@0.6 F4+Bb4:4 | G4+C5:4 | A4+E5:4 | A4+G5:4",
        "timp": "@0.85 " + cycle_timp(turn_chords),
        "perc": "@0.7 " + cycle_drums(4),
        "war": "@0.75 " + cycle_war(4),
        **danger_parts(turn_chords, war=False),
    })

    return song("Boarding Cadence", "D minor", voices,
                {"muster": muster, "riff": riff_section, "theme": theme, "stalk": stalk, "valor": valor, "turn": turn},
                ["muster", "riff", "theme", "stalk", "valor", "turn"])


# ---- Song two: Riggings Ablaze. E minor, big band brass over chip arpeggios, quicker on its feet. ----

def riggings_ablaze():
    voices = {
        "lead": voice("trumpet", 1.0, 0.1, echo=0.15),
        "sax": voice("sax", 0.9, -0.3),
        "bone": voice("trombone", 1.0, 0.25),
        "section": voice("trumpet_section", 0.75, -0.1),
        "ostinato": voice("strings_ostinato", 0.8, 0.35),
        "pad": voice("strings", 0.7, 0.0),
        "bass": voice("bass", 0.9, 0.0),
        "arp": voice("arp", 0.42, -0.4, arp=0.25, echo=0.2),
        "timp": voice("timpani", 0.4, -0.08),
        "perc": voice("drums", 0.65),
        "war": voice("drums", 0.5),
        **ORCH_DANGER,
    }

    fuse = section(2, "Em | B7", {
        "section": "@0.9 E4+G4+B4:1! r:3 | D#4+F#4+A4:1! r:1 D#4+F#4+B4:1/2! D#4+F#4+B4:1/2 D#4+F#4+B4:1/2 D#4+F#4+B4:1/2",
        "bone": "@0.85 E2:1! r:3 | B2:1! r:3",
        "bass": "@0.85 E2:4 | B1:4",
        "pad": "@0.55 E3+G3+B3:4 | D#3+F#3+A3:4",
        "timp": "@0.9 " + cycle_timp("Em | B7"),
        "perc": "@0.8 " + cycle_drums(2),
        "war": "@0.75 " + cycle_war(2),
    })

    chase_chords = "Em | D | C | B7 | Em | D | C B7 | Em"
    chase_riff = ("E3:1/2! E3:1/4 E3:1/4 G3:1/2 E3:1/2 B3:1/2! A3:1/2 G3:1/2 F#3:1/2 | "
                  "D3:1/2! D3:1/4 D3:1/4 F#3:1/2 D3:1/2 A3:1/2! G3:1/2 F#3:1/2 E3:1/2 | "
                  "C3:1/2! C3:1/4 C3:1/4 E3:1/2 C3:1/2 G3:1/2! F#3:1/2 E3:1/2 D3:1/2 | "
                  "B2:1/2! D#3:1/2 F#3:1/2 A3:1/2 B3:1! r:1 | "
                  "E3:1/2! E3:1/4 E3:1/4 G3:1/2 E3:1/2 B3:1/2! A3:1/2 G3:1/2 F#3:1/2 | "
                  "D3:1/2! D3:1/4 D3:1/4 F#3:1/2 D3:1/2 A3:1/2! G3:1/2 F#3:1/2 E3:1/2 | "
                  "C3:1/2! E3:1/2 G3:1/2 E3:1/2 B2:1/2! D#3:1/2 F#3:1/2 A3:1/2 | "
                  "E3:1! r:1/2 B2:1/2 E3:1/2! r:1/2 E2:1!")
    bars = bars_of(chase_chords)
    chase = section(8, chase_chords, {
        "bone": "@0.9 " + chase_riff,
        "section": "@0.72 " + join(offbeat_stabs(bar, 60) for bar in bars),
        "ostinato": "@0.62 " + join(gallop(bar, 64) for bar in bars),
        "bass": "@0.8 " + join(drive_332(bar, 28) for bar in bars),
        "arp": "@0.5 " + join(pad(bar, 64) for bar in bars),
        "timp": "@0.8 " + cycle_timp(chase_chords),
        "perc": "@0.62 " + cycle_drums(8),
        "war": "@0.7 " + cycle_war(8),
        **danger_parts(chase_chords),
    })

    hook_chords = "Em | Em | Am | Am | C | D | B7 | B7"
    bars = bars_of(hook_chords)
    hook = section(8, hook_chords, {
        "lead": "@0.95 B4:1/2! E5:1/2 G5:1/2 B5:1 A5:1/2 G5:1/2 F#5:1/2 | G5:3/2 E5:1/2 B4:2~ | "
                "C5:1/2! E5:1/2 A5:1/2 C6:1 B5:1/2 A5:1/2 G5:1/2 | A5:3/2 E5:1/2 C5:2~ | "
                "E5:1! G5:1/2 C6:1/2 E6:1 D6:1/2 C6:1/2 | D6:1 A5:1/2 F#5:1/2 D5:2 | D#5:1! F#5:1 A5:1 B5:1 | A5:1/2 F#5:1/2 D#5:1/2 B4:1/2 F#5:2-",
        "sax": "@0.72 G4:2 B4:2 | E4:2 G4:2 | E4:2 A4:2 | C4:2 E4:2 | G4:2 E4:2 | F#4:2 A4:2 | D#4:2 F#4:2 | A4:2 D#4:2",
        "section": "@0.7 " + join(offbeat_stabs(bar, 60) for bar in bars),
        "ostinato": "@0.58 " + join(runs(bar, 64) for bar in bars),
        "bass": "@0.8 " + join(drive_332(bar, 28) for bar in bars),
        "pad": "@0.45 " + join(pad(bar) for bar in bars),
        "arp": "@0.45 " + join(pad(bar, 64) for bar in bars),
        "timp": "@0.82 " + cycle_timp(hook_chords),
        "perc": "@0.68 " + cycle_drums(8),
        "war": "@0.66 " + cycle_war(8),
        **danger_parts(hook_chords),
    })

    smoke_chords = "Cmaj7 | Am7 | F#m7b5 | B7 | Cmaj7 | Am7 | F#m7b5 | B7"
    bars = bars_of(smoke_chords)
    smoke = section(8, smoke_chords, {
        "sax": "@0.9 E4:3/2! G4:1/2 B4:2 | C5:1 B4:1/2 A4:1/2 E4:2 | A4:3/2! C5:1/2 E5:2 | D#5:1 C5:1/2 B4:1/2 F#4:2 | "
               "G4:3/2! B4:1/2 E5:2~ | G5:1 E5:1/2 C5:1/2 A4:2 | C5:1 A4:1 F#4:1 E4:1 | D#4:1 F#4:1 A4:1 B4:1",
        "ostinato": "@0.55 " + join(gallop(bar, 64) for bar in bars),
        "bass": "@0.75 " + join(held_bass(bar, 28) for bar in bars),
        "pad": "@0.5 " + join(pad(bar) for bar in bars),
        "arp": "@0.36 " + join(pad(bar, 64) for bar in bars),
        "timp": "@0.7 " + cycle_timp(smoke_chords),
        "perc": "@0.5 " + cycle_drums(8, "march"),
        **danger_parts(smoke_chords, war=False),
    })

    sunbreak_chords = "G | D/F# | Em | C | G | D/F# | C D | G"
    bars = bars_of(sunbreak_chords)
    sunbreak = section(8, sunbreak_chords, {
        "lead": "@0.92 D5:1! G5:1 B5:3/2 A5:1/2 | A5:3~ F#5:1/2 D5:1/2 | E5:1/2 F#5:1/2 G5:1 B5:1 E6:1 | C6:3/2 B5:1/2 G5:1 E5:1 | "
                "B5:1! D6:1 B5:1 G5:1 | A5:1 F#5:1 D5:2 | E5:1 G5:1 F#5:1 A5:1 | G5:3~ D5:1",
        "sax": "@0.6 B3:2 D4:2 | A3:2 D4:2 | G3:2 B3:2 | G3:2 E4:2 | B3:2 D4:2 | A3:2 F#4:2 | G3:2 A3:2 | B3:2 D4:2",
        "pad": "@0.6 " + join(pad(bar) for bar in bars),
        "arp": "@0.5 " + join(pad(bar, 67) for bar in bars),
        "bass": "@0.7 " + join(held_bass(bar, 28) for bar in bars),
        "timp": "@0.55 " + cycle_timp(sunbreak_chords),
        "perc": "@0.55 " + cycle_drums(8, "lift"),
        "x_tremolo": "@0.36 " + join(tremolo(bar) for bar in bars),
    }, key="G major")

    turn_chords = "C | Am | B7 | B7"
    bars = bars_of(turn_chords)
    turn = section(4, turn_chords, {
        "section": "@0.95 C5+E5+G5:1/2! r:1/2 C5+E5+G5:1/2! r:1/2 C5+E5+G5:2- | A4+C5+E5:1/2! r:1/2 A4+C5+E5:1/2! r:1/2 A4+C5+E5:2- | "
                   "B4+D#5+F#5:1/2! r:1/2 B4+D#5+F#5:1/2! r:1/2 D#5+F#5+A5:1/2! r:1/2 D#5+F#5+A5:1/2! r:1/2 | D#5+F#5+B5:1! r:1 D#5+A5+B5:2-",
        "bone": "@0.9 C3:1! C3:1 E3:1 G3:1 | A2:1! C3:1 E3:1 A3:1 | B2:1! D#3:1 F#3:1 A3:1 | B3:1! A3:1/2 F#3:1/2 D#3:1 B2:1!",
        "ostinato": "@0.66 " + join(runs(bar, 64) for bar in bars),
        "bass": "@0.82 " + join(drive_332(bar, 28) for bar in bars),
        "pad": "@0.6 C4+E4+G4:4 | A3+C4+E4:4 | B3+D#4+F#4:4 | B3+D#4+A4:4",
        "timp": "@0.85 " + cycle_timp(turn_chords),
        "perc": "@0.72 " + cycle_drums(4),
        "war": "@0.75 " + cycle_war(4),
        **danger_parts(turn_chords, war=False),
    })

    return song("Riggings Ablaze", "E minor", voices,
                {"fuse": fuse, "chase": chase, "hook": hook, "smoke": smoke, "sunbreak": sunbreak, "turn": turn},
                ["fuse", "chase", "hook", "smoke", "sunbreak", "hook", "turn"])


# ---- Song three: Tyrant's Tempo. C minor, for captains and bosses: low brass, choir and war drums. ----

def tyrants_tempo():
    voices = {
        "trumpets": voice("orch_trumpets", 1.45, 0.1),
        "horns": voice("orch_horns", 1.05, -0.3),
        "bones": voice("orch_trombones", 1.05, 0.24),
        "tuba": voice("orch_tuba", 0.85, -0.04),
        "violins": voice("orch_violins", 1.9, -0.16),
        "spiccato": voice("orch_spiccato", 1.2, 0.3),
        "celli": voice("orch_celli", 0.85, -0.24),
        "basses": voice("orch_basses", 0.8, 0.0),
        "strings": voice("orch_strings", 0.9, 0.0),
        "choir": voice("orch_choir", 1.05, 0.0),
        "timp": voice("timpani", 0.45, -0.08),
        "perc": voice("drums", 0.64),
        "war": voice("drums", 0.58),
        **ORCH_DANGER,
    }

    toll = section(2, "Cm | G7", {
        "bones": "@0.9 C2+G2:1! r:3 | G2+D3:1! r:1 G2+B2+F3:1/2! G2+B2+F3:1/2 G2+B2+F3:1/2 G2+B2+F3:1/2",
        "tuba": "@0.9 C1:4 | G1:4",
        "choir": "@0.7 C4+Eb4+G4:4 | B3+D4+F4:4",
        "strings": "@0.6 C3+Eb3+G3:4 | B2+D3+F3:4",
        "timp": "@0.95 " + cycle_timp("Cm | G7"),
        "perc": "@0.85 gong+bdrum:1! field_snare:1/2 field_snare:1/4 field_snare:1/4 bdrum:1 field_snare:1 | " + CYCLE["march"][1],
        "war": "@0.8 " + cycle_war(2),
    })

    march_chords = "Cm | Cm | Db | G | Cm | Cm | Ab Db | G7"
    riff = ("C3:3/4! C3:3/4 G3:1/2! r:1/2 Eb3:1/2 D3:1/2 C3:1/2 | "
            "Eb3:3/4! D3:3/4 C3:1/2! r:1/2 G2:1/2 Ab2:1/2 B2:1/2 | "
            "Db3:3/4! Db3:3/4 Ab3:1/2! r:1/2 F3:1/2 Eb3:1/2 Db3:1/2 | "
            "D3:3/4! B2:3/4 G2:1/2! r:1/2 B2:1/2 D3:1/2 G3:1/2 | "
            "C3:3/4! C3:3/4 G3:1/2! r:1/2 Eb3:1/2 D3:1/2 C3:1/2 | "
            "G3:3/4! F3:3/4 Eb3:1/2! r:1/2 D3:1/2 Eb3:1/2 F3:1/2 | "
            "Ab2:3/4! C3:3/4 Eb3:1/2! Db3:3/4! F3:3/4 Ab3:1/2! | "
            "G3:1! F3:1/2 D3:1/2 B2:1 G2:1!")
    bars = bars_of(march_chords)
    march = section(8, march_chords, {
        "bones": "@0.92 " + riff,
        "tuba": "@0.72 " + join(held_bass(bar, 24) for bar in bars),
        "spiccato": "@0.66 " + join(gallop(bar) for bar in bars),
        "celli": "@0.75 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.75 " + join(drive_332(bar, 24) for bar in bars),
        "choir": "@0.5 " + join(pad(bar, 55) for bar in bars),
        "timp": "@0.85 " + cycle_timp(march_chords),
        "perc": "@0.62 " + cycle_drums(8, "march"),
        "war": "@0.78 " + cycle_war(8),
        **danger_parts(march_chords),
    })

    decree_chords = "Cm | Ab | Fm | G | Cm | Ab | Dm7b5 G7 | Cm G7"
    bars = bars_of(decree_chords)
    decree = section(8, decree_chords, {
        "trumpets": "@0.95 G4:1! C5:1 Eb5:1 D5:1/2 C5:1/2 | Eb5:2~ C5:1 Ab4:1 | F4:1! Ab4:1 C5:1 F5:1 | D5:3~ B4:1/2 D5:1/2 | "
                    "G5:1! Eb5:1/2 G5:1/2 C6:3/2 Bb5:1/2 | Ab5:2~ Eb5:1 C5:1 | F5:1 Ab5:1 G5:1 F5:1 | Eb5:3/2 D5:1/2 B4:2",
        "horns": "@0.8 Eb4:2 G4:2 | C4:2 Eb4:2 | C4:2 Ab4:2 | B3:2 D4:2 | Eb4:2 G4:2 | C4:2 Eb4:2 | Ab3:2 B3:2 | G3:2 F4:2",
        "bones": "@0.82 " + join(stabs_332(bar, 48) for bar in bars),
        "spiccato": "@0.64 " + join(runs(bar) for bar in bars),
        "celli": "@0.78 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.78 " + join(drive_332(bar, 24) for bar in bars),
        "tuba": "@0.72 " + join(held_bass(bar, 24) for bar in bars),
        "choir": "@0.62 " + join(pad(bar, 60) for bar in bars),
        "strings": "@0.5 " + join(pad(bar) for bar in bars),
        "timp": "@0.88 " + cycle_timp(decree_chords),
        "perc": "@0.68 " + cycle_drums(8),
        "war": "@0.72 " + cycle_war(8),
        **danger_parts(decree_chords),
    })

    vise_chords = "Fm | Fm | Db | C | Fm | Fm | Dm7b5 | G7"
    bars = bars_of(vise_chords)
    vise = section(8, vise_chords, {
        "horns": "@0.9 F3:3/2! Ab3:1/2 C4:2 | C4:1 Bb3:1/2 Ab3:1/2 F3:2 | Db4:3/2! F4:1/2 Ab4:2 | G4:1 E4:1 C4:2 | "
                 "F4:3/2! Ab4:1/2 C5:2~ | Eb5:1 C5:1/2 Bb4:1/2 Ab4:2 | Ab4:1 F4:1 D4:2 | B3:1 D4:1 F4:1 G4:1",
        "violins": "@0.55 r:4 | C6:1/2 Ab5:1/2 F5:1/2 C5:1/2 r:2 | r:4 | G5:1/2 E5:1/2 C5:1/2 G4:1/2 r:2 | "
                   "r:4 | C6:1/2 Ab5:1/2 F5:1/2 C5:1/2 r:2 | r:4 | B5:1/2 G5:1/2 F5:1/2 D5:1/2 B4:1/2 D5:1/2 F5:1/2 G5:1/2",
        "spiccato": "@0.62 " + join(gallop(bar) for bar in bars),
        "celli": "@0.68 " + join(drive_332(bar, 36) for bar in bars),
        "basses": "@0.7 " + join(held_bass(bar, 24) for bar in bars),
        "choir": "@0.5 " + join(pad(bar, 55) for bar in bars),
        "timp": "@0.78 " + cycle_timp(vise_chords),
        "perc": "@0.52 " + cycle_drums(8, "march"),
        **danger_parts(vise_chords, war=False),
    })

    defiance_chords = "Eb | Bb/D | Cm | Ab | Fm | Bb | Eb Ab | G"
    bars = bars_of(defiance_chords)
    defiance = section(8, defiance_chords, {
        "violins": "@0.9 Eb5:1! G5:1/2 Bb5:1/2 Eb6:2~ | D6:1 Bb5:1 F5:2 | G5:3/2 Ab5:1/2 G5:1 Eb5:1 | C5:3 Eb5:1 | "
                   "F5:1! Ab5:1/2 C6:1/2 F6:2~ | D6:1 C6:1/2 Bb5:1/2 F5:2 | Bb5:1 G5:1 C6:1 Ab5:1 | B5:2~ D6:1 G5:1",
        "horns": "@0.64 G3:2 Bb3:2 | F3:2 Bb3:2 | Eb3:2 G3:2 | Eb3:2 C4:2 | F3:2 Ab3:2 | F3:2 D4:2 | G3:2 Ab3:2 | G3:2 B3:2",
        "strings": "@0.6 " + join(pad(bar) for bar in bars),
        "choir": "@0.62 " + join(pad(bar, 60) for bar in bars),
        "celli": "@0.62 " + join(held_bass(bar, 36) for bar in bars),
        "basses": "@0.62 " + join(held_bass(bar, 24) for bar in bars),
        "timp": "@0.6 " + cycle_timp(defiance_chords),
        "perc": "@0.55 " + cycle_drums(8, "lift"),
        "x_tremolo": "@0.38 " + join(tremolo(bar) for bar in bars),
    }, key="Eb major")

    turn_chords = "Ab | Db | G7 | G7"
    bars = bars_of(turn_chords)
    turn = section(4, turn_chords, {
        "trumpets": "@0.95 Eb5+Ab5+C6:1/2! r:1/2 Eb5+Ab5+C6:1/2! r:1/2 Eb5+Ab5+C6:2- | F5+Ab5+Db6:1/2! r:1/2 F5+Ab5+Db6:1/2! r:1/2 F5+Ab5+Db6:2- | "
                    "D5+G5+B5:1/2! r:1/2 D5+G5+B5:1/2! r:1/2 F5+G5+B5:1/2! r:1/2 F5+G5+B5:1/2! r:1/2 | D5+F5+B5:1! r:1 D5+G5+B5:2-",
        "horns": "@0.85 Ab3+Eb4:4 | Ab3+F4:4 | G3+D4:4 | G3+F4:4",
        "bones": "@0.92 Ab2:1! Ab2:1 C3:1 Eb3:1 | Db3:1! Db3:1 F3:1 Ab3:1 | G2:1! B2:1 D3:1 F3:1 | G3:1! F3:1/2 D3:1/2 B2:1 G2:1!",
        "spiccato": "@0.7 " + join(runs(bar) for bar in bars),
        "tuba": "@0.82 Ab1:4 | Db2:4 | G1:4 | G1:4",
        "basses": "@0.82 " + join(drive_332(bar, 24) for bar in bars),
        "choir": "@0.66 Eb4+Ab4+C5:4 | F4+Ab4+Db5:4 | D4+G4+B4:4 | F4+G4+B4:4",
        "timp": "@0.9 " + cycle_timp(turn_chords),
        "perc": "@0.74 " + cycle_drums(4),
        "war": "@0.8 " + cycle_war(4),
        **danger_parts(turn_chords, war=False),
    })

    return song("Tyrant's Tempo", "C minor", voices,
                {"toll": toll, "march": march, "decree": decree, "vise": vise, "defiance": defiance, "turn": turn},
                ["toll", "march", "decree", "vise", "defiance", "turn"])


SONGS = {"boarding_cadence": boarding_cadence, "riggings_ablaze": riggings_ablaze, "tyrants_tempo": tyrants_tempo}


def main():
    for slug, build in SONGS.items():
        (HERE / f"{slug}.json").write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
        print("wrote", slug)


if __name__ == "__main__":
    main()
