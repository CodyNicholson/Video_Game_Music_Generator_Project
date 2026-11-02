#!/usr/bin/env python3
"""Writes the dogfight scores to music/*.json. The melodies are written out by hand below, and this
file fills in the repeating accompaniment (ostinatos, stabs, drums), which would run to thousands of
tokens in JSON. Edit here and re-run it, then render the JSON with the chiptune-composer skill."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
      "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
QUALITY = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "dim": (0, 3, 6),
           "m7b5": (0, 3, 6, 10), "sus4": (0, 5, 7)}


def split_chord(chord):
    chord = chord.split("/")[0]
    root = chord[:2] if chord[1:2] in ("b", "#") else chord[:1]
    return PC[root], chord[len(root):]


def name(midi):
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def tones(chord, low):
    """The chord's tones, ascending from the first one at or above the low MIDI note."""
    root, quality = split_chord(chord)
    out = []
    for interval in QUALITY[quality]:
        pitch = low + (root + interval - low) % 12
        out.append(pitch)
    return sorted(out)


def root(chord, low):
    bass = chord.split("/")[1] if "/" in chord else None
    pc = PC[bass] if bass else split_chord(chord)[0]
    return low + (pc - low) % 12


def bars_of(chords):
    return [bar.strip().split() for bar in chords.split("|")]


def join(bars):
    return " | ".join(bars)


# ---- Accompaniment for 4/4. Each takes one bar's chords and gives one bar of notes. ----

def per_half(bar):
    return [bar[0], bar[0]] if len(bar) == 1 else bar


def gallop(bar, low=62):
    """Spiccato eighth and two sixteenths, walking through the chord."""
    out = []
    for i, chord in enumerate(per_half(bar)):
        t = tones(chord, low)
        for j, note in enumerate((t[0], t[1 + i])):
            out += [f"{name(note)}:1/2{'!' if i == 0 and j == 0 else ''}", f"{name(t[0])}:1/4", f"{name(t[0])}:1/4"]
    return " ".join(out)


def runs(bar, low=62):
    """Rising sixteenth arpeggios, for when the music should feel like it is climbing."""
    out = []
    for i, chord in enumerate(per_half(bar)):
        t = tones(chord, low)[:3]
        cycle = [t[0], t[1], t[2], t[0] + 12, t[2], t[1], t[2], t[0] + 12]
        out += [f"{name(p)}:1/4{'!' if k == 0 and i == 0 else ''}" for k, p in enumerate(cycle)]
    return " ".join(out)


def drive_332(bar, low):
    """Eighths accented 3+3+2, the pulse under most of the battle."""
    out = []
    chords = [bar[0]] * 4 + [bar[-1]] * 4
    for i, chord in enumerate(chords):
        out.append(f"{name(root(chord, low))}:1/2{'!' if i in (0, 3, 6) else ''}")
    return " ".join(out)


def held_bass(bar, low):
    return " ".join(f"{name(root(chord, low))}:{4 // len(bar)}" for chord in bar)


def pad(bar, low=55):
    return " ".join("+".join(name(p) for p in tones(chord, low)[:4]) + f":{4 // len(bar)}" for chord in bar)


def stabs_332(bar, low=48):
    """Short brass chords on the 3+3+2 accents."""
    a = "+".join(name(p) for p in tones(bar[0], low)[:3])
    b = "+".join(name(p) for p in tones(bar[-1], low)[:3])
    return f"{a}:1/2! r:1 {a}:1/2! r:1 {b}:1/2! r:1/2"


def offbeat_stabs(bar, low=60):
    a = "+".join(name(p) for p in tones(bar[0], low)[:3])
    b = "+".join(name(p) for p in tones(bar[-1], low)[:3])
    return f"r:1/2 {a}:1/2! r:1/2 {a}:1/2 r:1/2 {b}:1/2! r:1/2 {b}:1/2"


def harp_sweep(bar, low=48):
    out = []
    for chord in per_half(bar):
        t = tones(chord, low)[:3]
        out += [f"{name(p)}:1/4" for p in (t[0], t[1], t[2], t[0] + 12, t[1] + 12, t[2] + 12, t[0] + 24, t[2] + 12)]
    return " ".join(out)


def tremolo(bar, low=76):
    return " ".join(f"{name(tones(chord, low)[0])}:{4 // len(bar)}" for chord in bar)


BEAT = "bdrum:1 field_snare:1/2 field_snare:1/4 field_snare:1/4 bdrum:1/2 bdrum:1/2 field_snare:1"
WAR = "taiko:1! taiko_hi:1/2 taiko_hi:1/2 r:1/2 taiko:1/2! taiko_hi:1/4 taiko_hi:1/4 taiko:1/2"
FILL = "{field_snare:1/4}*8 tom_hi:1/4 tom_hi:1/4 tom_hi:1/4 tom_hi:1/4 tom_lo:1/4 tom_lo:1/4 taiko:1/2!"


# ---- Song one: Wings of the Tempest. C minor, straight, a brass-led charge. ----

def voice(instrument, gain=1.0, pan=0.0, **extra):
    return {"instrument": instrument, "gain": gain, "pan": pan, **extra}


TEMPEST_VOICES = {
    "trumpets": voice("orch_trumpets", 1.4, 0.12),
    "horns": voice("orch_horns", 1.05, -0.32),
    "bones": voice("orch_trombones", 1.0, 0.24),
    "tuba": voice("orch_tuba", 0.8, -0.04),
    "violins": voice("orch_violins", 1.9, -0.16),
    "spiccato": voice("orch_spiccato", 1.25, 0.3),
    "celli": voice("orch_celli", 0.85, -0.24),
    "basses": voice("orch_basses", 0.75, 0.0),
    "strings": voice("orch_strings", 0.95, 0.0),
    "choir": voice("orch_choir", 1.0, 0.0),
    "winds": voice("orch_winds", 0.8, 0.38),
    "harp": voice("harp", 0.85, -0.42),
    "bells": voice("bell", 0.7, 0.42),
    "timp": voice("timpani", 0.38, -0.08),
    "perc": voice("drums", 0.62),
    "war": voice("drums", 0.5, 0.0),
    "x_tremolo": voice("orch_tremolo", 1.8, -0.36, layer="danger"),
    "x_bones": voice("orch_trombones", 0.72, 0.36, layer="danger"),
    "x_war": voice("drums", 0.62, 0.15, layer="danger"),
}


def danger_parts(chords, bones=True, war=True):
    bars = bars_of(chords)
    parts = {"x_tremolo": "@0.5 " + join(tremolo(bar) for bar in bars)}
    if bones:
        parts["x_bones"] = "@0.8 " + join(stabs_332(bar) for bar in bars)
    if war:
        parts["x_war"] = "@0.6 " + join(["taiko_hi:1/2 taiko_hi:1/4 taiko_hi:1/4 field_snare:1/2 taiko_hi:1/2 taiko_hi:1/2 taiko_hi:1/4 taiko_hi:1/4 field_snare:1/2 taiko_hi:1/2"] * len(bars))
    return parts


def tempest():
    alarm_chords = "G | G | Ab | G7"
    alarm = {
        "bars": 4, "chords": alarm_chords,
        "parts": {
            "trumpets": "@0.9 G4:1/4! G4:1/4 G4:1/2 C5:1! G5:2~ | r:1 G4:1/4 G4:1/4 G4:1/2 B4:1! D5:1 | Ab4:1/4! Ab4:1/4 Ab4:1/2 C5:1! Eb5:2~ | D5:1! B4:1/2 D5:1/2 G5:2-",
            "horns": "@0.85 G3+D4:4 | G3+D4:4 | Ab3+Eb4:4 | G3+D4:2 G3+F4:2",
            "bones": "@0.85 G2+D3:4 | G2+D3:2 G2+B2+D3:1/2! r:1/2 G2+B2+D3:1/2! r:1/2 | Ab2+Eb3:4 | G2+D3:1/2! r:1/2 G2+D3:1/2! r:1/2 G2+D3+F3:2-",
            "tuba": "@0.85 G1:4 | G1:4 | Ab1:4 | G1:4",
            "strings": "@0.65 G3+B3+D4:4 | G3+B3+D4:4 | Ab3+C4+Eb4:4 | G3+B3+F4:4",
            "timp": "@0.9 G2:1! r:3 | {G2:1/4}*16 | Ab2:1! r:3 | {G2:1/4}*12 G2:1!",
            "perc": "@0.85 gong:1 r:3 | swell:4 | cymbal:1 r:3 | snare_roll:3 taiko:1!",
            "war": "@0.7 taiko:1! r:3 | r:2 taiko:1/2 taiko:1/2 taiko:1/2 taiko_hi:1/2 | taiko:1! r:3 | r:2 taiko:1/2 taiko_hi:1/2 taiko:1/2 taiko_hi:1/2",
        },
    }

    riff_chords = "Cm | Cm | Ab | G | Cm | Cm | Fm Db | G7"
    riff = ("C3:1/2! r:1/4 C3:1/4 Eb3:1/2! r:1/4 Eb3:1/4 G3:1! F3:1/2 Eb3:1/2 | "
            "D3:1/2 Eb3:1/2 C3:1! r:1/2 G2:1/2 Ab2:1/2 B2:1/2 | "
            "Ab2:1/2! r:1/4 Ab2:1/4 C3:1/2! r:1/4 C3:1/4 Eb3:1! D3:1/2 C3:1/2 | "
            "B2:1/2 C3:1/2 D3:1 G3:3/2! r:1/2 | "
            "C3:1/2! r:1/4 C3:1/4 Eb3:1/2! r:1/4 Eb3:1/4 G3:1! Ab3:1/2 G3:1/2 | "
            "F3:1/2 G3:1/2 Eb3:1 r:1/2 C3:1/2 D3:1/2 Eb3:1/2 | "
            "F3:1! Ab3:1 Db3:1! F3:1 | G3:1! F3:1/2 D3:1/2 B2:1 G2:1!")
    bars = bars_of(riff_chords)
    scramble = {
        "bars": 8, "chords": riff_chords,
        "parts": {
            "bones": "@0.9 " + riff,
            "horns": "@0.72 " + riff.replace("3:", "#").replace("2:", "3:").replace("#", "4:"),
            "spiccato": "@0.68 " + join(gallop(bar) for bar in bars),
            "celli": "@0.75 " + join(drive_332(bar, 36) for bar in bars),
            "basses": "@0.75 " + join(drive_332(bar, 24) for bar in bars),
            "tuba": "@0.65 " + join(held_bass(bar, 24) for bar in bars),
            "strings": "@0.42 " + join(pad(bar) for bar in bars),
            "timp": "@0.8 C3:1! r:3 | r:2 C3:1/2 C3:1/2 C3:1! | Ab2:1! r:3 | {G2:1/4}*8 G2:2! | C3:1! r:3 | r:2 C3:1/2 C3:1/2 C3:1! | F2:1! r:1 Db3:1! r:1 | {G2:1/4}*12 G2:1!",
            "perc": "@0.58 " + join([BEAT] * 7 + [FILL]),
            "war": "@0.72 " + join([WAR] * 7 + ["r:4"]),
            **danger_parts(riff_chords),
        },
    }

    def theme(big):
        chords = "Cm | Ab | Eb | Bb | Cm | Ab | Fm G7 | Cm G7"
        bars = bars_of(chords)
        melody = ("C5:3/2! G5:1/2 G5:1 Eb5:1/2 F5:1/2 | "
                  "Eb5:3/2! Ab5:1/2 Ab5:1 G5:1/2 F5:1/2 | "
                  "G5:2~ Bb5:1/2 G5:1/2 Eb5:1 | "
                  "F5:5/2~ D5:1/2 Bb4:1/2 D5:1/2 | "
                  "C5:3/2! G5:1/2 G5:1 Eb5:1/2 F5:1/2 | "
                  "Ab5:3/2! C6:1/2 C6:1 Bb5:1/2 Ab5:1/2 | "
                  "C6:1 Ab5:1/2 C6:1/2 B5:1 D6:1 | "
                  "Eb6:1! D6:1/2 C6:1/2 B5:1 G5:1")
        counter = ("Eb4:2 G4:2 | C4:2 Eb4:2 | Eb4:1 G4:1 Bb4:2 | D4:1 F4:1 Bb4:2 | "
                   "Eb4:2 G4:2 | Eb4:2 Ab4:2 | Ab4:2 B4:2 | G4:2 D4:2")
        parts = {
            "trumpets": "@0.95 " + melody,
            "horns": "@0.8 " + counter,
            "bones": "@0.8 " + join(offbeat_stabs(bar, 48) for bar in bars),
            "spiccato": "@0.66 " + join(runs(bar) for bar in bars),
            "celli": "@0.78 " + join(drive_332(bar, 36) for bar in bars),
            "basses": "@0.78 " + join(drive_332(bar, 24) for bar in bars),
            "tuba": "@0.72 " + join(held_bass(bar, 24) for bar in bars),
            "strings": "@0.5 " + join(pad(bar) for bar in bars),
            "timp": "@0.85 C3:1! r:3 | Ab2:1! r:3 | Eb3:1! r:3 | Bb2:1! r:3 | C3:1! r:3 | Ab2:1! r:3 | F2:1! r:1 G2:1! r:1 | C3:1! r:2 G2:1/2 G2:1/2",
            "perc": "@0.68 cymbal+bdrum:1! field_snare:1/2 field_snare:1/4 field_snare:1/4 bdrum:1/2 bdrum:1/2 field_snare:1 | " + join([BEAT] * 3) + " | cymbal+bdrum:1! field_snare:1/2 field_snare:1/4 field_snare:1/4 bdrum:1/2 bdrum:1/2 field_snare:1 | " + join([BEAT] * 2) + " | " + FILL,
            "war": "@0.68 " + join([WAR] * 7 + ["r:4"]),
            **danger_parts(chords),
        }
        if big:
            # The return: violins an octave over the trumpets, the choir and bells joining in.
            octave_up = (("C6:3/2! G6:1/2 G6:1 Eb6:1/2 F6:1/2 | Eb6:3/2! Ab6:1/2 Ab6:1 G6:1/2 F6:1/2 | G6:2~ Bb6:1/2 G6:1/2 Eb6:1 | "
                          "F6:5/2~ D6:1/2 Bb5:1/2 D6:1/2 | C6:3/2! G6:1/2 G6:1 Eb6:1/2 F6:1/2 | Ab6:3/2! C7:1/2 C7:1 Bb6:1/2 Ab6:1/2 | "
                          "C7:1 Ab6:1/2 C7:1/2 B6:1 D7:1 | Eb7:1! D7:1/2 C7:1/2 B6:1 G6:1"))
            parts["violins"] = "@0.82 " + octave_up
            parts["choir"] = "@0.62 " + join(pad(bar, 60) for bar in bars)
            parts["bells"] = "@0.6 C6:1 r:3 | C6:1 r:3 | Eb6:1 r:3 | D6:1 r:3 | C6:1 r:3 | C6:1 r:3 | C6:1 r:1 B5:1 r:1 | C6:1 r:3"
        return {"bars": 8, "chords": chords, "parts": parts}

    dive_chords = "Fm | Db | Ab | Eb | Fm | Db | Dm7b5 | G7"
    bars = bars_of(dive_chords)
    dive = {
        "bars": 8, "chords": dive_chords,
        "parts": {
            "horns": "@0.92 F4:3/2! C5:1/2 C5:2 | Db5:1 C5:1/2 Bb4:1/2 Ab4:2 | C5:3/2! Eb5:1/2 Eb5:2 | Bb4:1 G4:1 Eb4:2 | F4:3/2! Ab4:1/2 C5:1 F5:1 | F5:1 Eb5:1/2 Db5:1/2 Ab4:2 | Ab4:1 F4:1/2 Ab4:1/2 D5:2 | D5:1 F5:1 G5:2-",
            "trumpets": "@0.85 r:4 | r:2 Ab4+Db5+F5:1/2! r:1/2 Ab4+Db5+F5:1/2! r:1/2 | r:4 | r:2 G4+Bb4+Eb5:1/2! r:1/2 G4+Bb4+Eb5:1/2! r:1/2 | r:4 | r:2 Ab4+Db5+F5:1/2! r:1/2 Ab4+Db5+F5:1/2! r:1/2 | r:2 Ab4+C5+D5:1/2! r:1/2 Ab4+C5+D5:1/2! r:1/2 | B4+D5+F5:1/2! r:1/2 B4+D5+F5:1/2! r:1/2 B4+D5+G5:2-",
            "winds": "@0.72 r:2 F5:1/4 Ab5:1/4 C6:1/4 F6:1/4 Ab6:1 | r:2 F5:1/4 Ab5:1/4 Db6:1/4 F6:1/4 Ab6:1 | r:2 Eb5:1/4 Ab5:1/4 C6:1/4 Eb6:1/4 Ab6:1 | r:2 Eb5:1/4 G5:1/4 Bb5:1/4 Eb6:1/4 G6:1 | r:2 F5:1/4 Ab5:1/4 C6:1/4 F6:1/4 Ab6:1 | r:2 F5:1/4 Ab5:1/4 Db6:1/4 F6:1/4 Ab6:1 | r:2 D5:1/4 F5:1/4 Ab5:1/4 D6:1/4 F6:1 | G5:1/4 B5:1/4 D6:1/4 F6:1/4 G6:1/4 F6:1/4 D6:1/4 B5:1/4 G5:1/4 B5:1/4 D6:1/4 F6:1/4 G6:1",
            "spiccato": "@0.6 " + join(gallop(bar) for bar in bars),
            "celli": "@0.68 " + join(drive_332(bar, 36) for bar in bars),
            "basses": "@0.7 " + join(held_bass(bar, 24) for bar in bars),
            "strings": "@0.5 " + join(pad(bar) for bar in bars),
            "timp": "@0.75 F2:1! r:3 | Db3:1! r:3 | Ab2:1! r:3 | Eb3:1! r:3 | F2:1! r:3 | Db3:1! r:3 | D3:1! r:3 | {G2:1/4}*12 G2:1!",
            "perc": "@0.5 " + join(["bdrum:1 r:1 field_snare:1/2 field_snare:1/2 r:1"] * 7 + [FILL]),
            **danger_parts(dive_chords, war=False),
        },
    }

    heart_chords = "Eb | Bb/D | Cm | Ab | Fm | Bb | Eb Ab | Bb"
    bars = bars_of(heart_chords)
    heart = {
        "bars": 8, "key": "Eb major", "chords": heart_chords,
        "parts": {
            "violins": "@0.88 G5:3~ Bb5:1/2 Ab5:1/2 | F5:3~ D5:1/2 Eb5:1/2 | Eb5:1 G5:1 C6:2~ | C6:1 Bb5:1/2 Ab5:1/2 Eb5:2 | F5:1 Ab5:1 C6:2~ | D6:1 C6:1/2 Bb5:1/2 F5:2 | G5:1 Bb5:1 Eb6:1 C6:1 | D6:2~ Bb5:1 F5:1",
            "horns": "@0.62 Eb4:2 G4:2 | D4:2 F4:2 | Eb4:2 G4:2 | Eb4:2 Ab4:2 | C4:2 F4:2 | D4:2 F4:2 | Eb4:2 Eb4:2 | D4:2 F4:2",
            "harp": "@0.62 " + join(harp_sweep(bar) for bar in bars),
            "strings": "@0.6 " + join(pad(bar) for bar in bars),
            "choir": "@0.58 " + join(pad(bar, 60) for bar in bars),
            "celli": "@0.6 " + join(held_bass(bar, 36) for bar in bars),
            "basses": "@0.6 " + join(held_bass(bar, 24) for bar in bars),
            "bells": "@0.5 G6:2 r:2 | F6:2 r:2 | G6:2 r:2 | Eb6:2 r:2 | F6:2 r:2 | F6:2 r:2 | G6:2 r:2 | F6:2 r:2",
            "timp": "@0.55 Eb3:1 r:3 | r:4 | C3:1 r:3 | Ab2:1 r:3 | F2:1 r:3 | Bb2:1 r:3 | Eb3:1 r:1 Ab2:1 r:1 | {Bb2:1/4}*16",
            "perc": "@0.55 cymbal:1 r:3 | r:4 | bdrum:1 r:3 | r:4 | bdrum:1 r:3 | r:4 | bdrum:1 r:3 | swell:4",
            "x_tremolo": "@0.36 " + join(tremolo(bar) for bar in bars),
        },
    }

    rise_chords = "Bb | C | A7 | A7"
    rise = {
        "bars": 4, "key": "D minor", "chords": rise_chords,
        "parts": {
            "trumpets": "@0.85 D5:1! F5:1 Bb5:2 | E5:1! G5:1 C6:2 | C#5+E5+A5:1/2! r:1/2 C#5+E5+A5:1/2! r:1/2 E5+G5+C#6:1/2! r:1/2 E5+G5+C#6:1/2! r:1/2 | G5+A5+E6:1/2! G5+A5+E6:1/2 G5+A5+E6:1/2 G5+A5+E6:1/2 G5+A5+E6:2-",
            "horns": "@0.8 Bb3+F4:4 | C4+G4:4 | A3+E4:4 | A3+G4:4",
            "bones": "@0.9 Bb2:1! Bb2:1 Bb2:1 D3:1 | C3:1! C3:1 E3:1 G3:1 | A2:1! C#3:1 E3:1 G3:1 | A3:1! G3:1/2 E3:1/2 C#3:1 A2:1!",
            "spiccato": "@0.72 " + join(["{Bb4:1/4}*16", "{C5:1/4}*16", "{C#5:1/4}*16", "{E5:1/4}*16"]),
            "tuba": "@0.8 Bb1:4 | C2:4 | A1:4 | A1:4",
            "basses": "@0.8 " + join(["{Bb1:1/2}*8", "{C2:1/2}*8", "{A1:1/2}*8", "{A1:1/2}*8"]),
            "strings": "@0.62 Bb3+D4+F4:4 | C4+E4+G4:4 | A3+C#4+E4:4 | A3+C#4+G4:4",
            "choir": "@0.6 F4+Bb4:4 | G4+C5:4 | A4+E5:4 | A4+G5:4",
            "timp": "@0.85 {Bb2:1/4}*16 | {C3:1/4}*16 | {A2:1/4}*16 | {A2:1/4}*12 A2:1!",
            "perc": "@0.7 swell:4 | snare_roll:4 | snare_roll:4 | " + FILL,
            "war": "@0.75 taiko:1! r:3 | taiko:1! r:3 | taiko:1! taiko:1! taiko:1! taiko:1! | {taiko:1/2}*8",
            "x_tremolo": "@0.5 D6:4 | E6:4 | E6:4 | A6:4",
        },
    }

    turn_chords = "Bb | Ab | G7 | G7"
    turn = {
        "bars": 4, "chords": turn_chords,
        "parts": {
            "trumpets": "@0.95 D5+F5+Bb5:1/2! r:1/2 D5+F5+Bb5:1/2! F5+Bb5+D6:5/2- | Eb5+Ab5+C6:1/2! r:1/2 Eb5+Ab5+C6:1/2! C5+Eb5+Ab5:5/2- | D5+G5+B5:1/2! r:1/2 D5+G5+B5:1/2! r:1/2 D5+G5+B5:1/2! r:1/2 D5+F5+B5:1/2! r:1/2 | D5+G5+B5:1! F5+G5+D6:3-",
            "horns": "@0.85 Bb3+F4:4 | Ab3+Eb4:4 | G3+D4:4 | G3+F4:4",
            "bones": "@0.9 Bb2+F3:1/2! r:1 Bb2+F3:1/2! r:1 Bb2+F3:1/2! r:1/2 | Ab2+Eb3:1/2! r:1 Ab2+Eb3:1/2! r:1 Ab2+Eb3:1/2! r:1/2 | G2+D3:1/2! r:1 G2+D3:1/2! r:1 G2+D3:1/2! r:1/2 | G2+D3+F3:1! G2+B2+F3:3-",
            "spiccato": "@0.7 " + join(runs(bar) for bar in bars_of(turn_chords)),
            "celli": "@0.8 " + join(drive_332(bar, 36) for bar in bars_of(turn_chords)),
            "basses": "@0.8 " + join(drive_332(bar, 24) for bar in bars_of(turn_chords)),
            "tuba": "@0.8 Bb1:4 | Ab1:4 | G1:4 | G1:4",
            "strings": "@0.6 Bb3+D4+F4:4 | Ab3+C4+Eb4:4 | G3+B3+D4:4 | G3+B3+F4:4",
            "choir": "@0.6 F4+Bb4:4 | Eb4+Ab4:4 | D4+G4:4 | F4+G4:4",
            "timp": "@0.9 Bb2:1! r:3 | Ab2:1! r:3 | G2:1! r:3 | {G2:1/4}*12 G2:1!",
            "perc": "@0.75 cymbal+bdrum:1! field_snare:1/2 field_snare:1/4 field_snare:1/4 bdrum:1/2 bdrum:1/2 field_snare:1 | " + BEAT + " | snare_roll:4 | " + FILL,
            "war": "@0.78 " + WAR + " | " + WAR + " | {taiko:1/2}*8 | {taiko:1/2}*6 taiko:1! ",
            **danger_parts(turn_chords, bones=False, war=False),
        },
    }

    return {
        "title": "Wings of the Tempest", "bpm": 168, "meter": "4/4", "key": "C minor", "loop_from": 1,
        "voices": TEMPEST_VOICES,
        "sections": {"alarm": alarm, "scramble": scramble, "theme": theme(False), "dive": dive, "heart": heart,
                     "rise": rise, "theme_big": theme(True), "turn": turn},
        "arrangement": ["alarm", "scramble", "theme", "dive", "heart", "rise", {"section": "theme_big", "transpose": 2}, "turn"],
    }


# ---- Song two: Gauntlet of Thunderheads. E minor in a galloping 6/8, darker and more relentless. ----

def six_gallop(bar, low=59):
    """Two groups of three eighths per bar: root, root, chord tone."""
    out = []
    for i, chord in enumerate([bar[0], bar[-1]]):
        t = tones(chord, low)
        out += [f"{name(t[0])}:1/2{'!' if i == 0 else ''}", f"{name(t[0])}:1/2", f"{name(t[1 + i])}:1/2"]
    return " ".join(out)


def six_arp(bar, low=62):
    out = []
    for i, chord in enumerate([bar[0], bar[-1]]):
        t = tones(chord, low)[:3]
        seq = (t[0], t[1], t[2]) if i == 0 else (t[0] + 12, t[2], t[1])
        out += [f"{name(p)}:1/2{'!' if k == 0 else ''}" for k, p in enumerate(seq)]
    return " ".join(out)


def six_bass(bar, low):
    out = []
    for chord in [bar[0], bar[-1]]:
        r = name(root(chord, low))
        out += [f"{r}:1/2!", f"{r}:1/2", f"{r}:1/2"]
    return " ".join(out)


def six_held(bar, low):
    return " ".join(f"{name(root(chord, low))}:{3 if len(bar) == 1 else '3/2'}" for chord in bar)


def six_pad(bar, low=55):
    return " ".join("+".join(name(p) for p in tones(chord, low)[:4]) + f":{3 if len(bar) == 1 else '3/2'}" for chord in bar)


def six_stabs(bar, low=48):
    a = "+".join(name(p) for p in tones(bar[0], low)[:3])
    b = "+".join(name(p) for p in tones(bar[-1], low)[:3])
    return f"{a}:1/2! r:1 {b}:1/2! r:1"


def six_tremolo(bar, low=76):
    return " ".join(f"{name(tones(chord, low)[0])}:{3 if len(bar) == 1 else '3/2'}" for chord in bar)


SIX_BEAT = "bdrum:1/2 field_snare:1/4 field_snare:1/4 field_snare:1/2 bdrum:1/2 field_snare:1/2 field_snare:1/2"
SIX_WAR = "taiko:1! taiko_hi:1/2 taiko:1/2! taiko_hi:1/2 taiko_hi:1/2"
SIX_FILL = "{field_snare:1/4}*6 tom_hi:1/2 tom_lo:1/2 taiko:1/2!"


def thunder_danger(chords):
    bars = bars_of(chords)
    return {
        "x_tremolo": "@0.5 " + join(six_tremolo(bar) for bar in bars),
        "x_bones": "@0.8 " + join(six_stabs(bar) for bar in bars),
        "x_war": "@0.6 " + join([SIX_BEAT.replace("bdrum", "taiko_hi")] * len(bars)),
    }


def thunderheads():
    voices = {**TEMPEST_VOICES, "trumpets": voice("orch_trumpets", 1.4, -0.1), "spiccato": voice("orch_spiccato", 1.25, -0.3),
              "horns": voice("orch_horns", 1.05, 0.3), "bones": voice("orch_trombones", 1.0, -0.22), "winds": voice("orch_winds", 0.85, 0.4)}

    gather = {
        "bars": 4, "chords": "Em | Em | C | B7",
        "parts": {
            "horns": "@0.85 E3+B3:3 | E3+B3:3 | C4+G4:3 | B3+F#4:3/2 B3+A4:3/2",
            "bones": "@0.8 r:3 | r:3 | C3+G3:3 | B2+F#3:1/2! r:1/2 B2+F#3:1/2! B2+A3:3/2-",
            "tuba": "@0.85 E1:3 | E1:3 | C2:3 | B1:3",
            "strings": "@0.55 E3+B3+E4:3 | E3+B3+G4:3 | C4+E4+G4:3 | B3+D#4+A4:3",
            "spiccato": "@0.6 r:3 | r:3 | {C4:1/2}*6 | {B3:1/2}*6",
            "timp": "@0.9 E3:1! r:2 | {E3:1/4}*12 | C3:1! r:2 | {B2:1/4}*10 B2:1/2!",
            "perc": "@0.85 gong:1 r:2 | swell:3 | cymbal:1 r:2 | snare_roll:5/2 taiko:1/2!",
            "war": "@0.7 taiko:1! r:2 | r:3/2 taiko:1/2 taiko:1/2 taiko_hi:1/2 | taiko:1! r:2 | taiko:1/2 taiko:1/2 taiko:1/2 taiko:1/2 taiko_hi:1/2 taiko_hi:1/2",
        },
    }

    hunt_chords = "Em | Em | C | B7 | Em | Em | Am C | B7"
    bars = bars_of(hunt_chords)
    hunt = {
        "bars": 8, "chords": hunt_chords,
        "parts": {
            # The theme, low and quiet in the horns, before the trumpets take it.
            "horns": "@0.86 B3:1/2! E4:1/2 G4:1/2 B4:1 A4:1/2 | G4:1/2 F#4:1/2 E4:1/2 B3:3/2 | G4:1/2! E4:1/2 C4:1/2 G4:1 E4:1/2 | D#4:3/2! F#4:1/2 A4:1/2 F#4:1/2 | B3:1/2! E4:1/2 G4:1/2 B4:1 A4:1/2 | G4:1/2 A4:1/2 B4:1/2 E5:3/2 | E5:1/2 C5:1/2 A4:1/2 G4:1/2 E4:1/2 C4:1/2 | B3:1 D#4:1/2 F#4:1 B4:1/2",
            "spiccato": "@0.68 " + join(six_gallop(bar) for bar in bars),
            "celli": "@0.76 " + join(six_bass(bar, 28) for bar in bars),
            "basses": "@0.74 " + join(six_held(bar, 24) for bar in bars),
            "strings": "@0.42 " + join(six_pad(bar) for bar in bars),
            "timp": "@0.76 E3:1! r:2 | r:2 E3:1/2 E3:1/2 | C3:1! r:2 | B2:1! r:1 B2:1/2 B2:1/2 | E3:1! r:2 | r:2 E3:1/2 E3:1/2 | A2:1! r:1/2 C3:1! r:1/2 | {B2:1/4}*10 B2:1/2!",
            "perc": "@0.52 " + join([SIX_BEAT] * 7 + [SIX_FILL]),
            "war": "@0.7 " + join([SIX_WAR] * 7 + ["r:3"]),
            **thunder_danger(hunt_chords),
        },
    }

    def chase_part(melody, counter, chords, winds=None, crash_bars=(0, 4)):
        bars = bars_of(chords)
        perc = []
        for i in range(len(bars)):
            if i == len(bars) - 1:
                perc.append(SIX_FILL)
            elif i in crash_bars:
                perc.append(SIX_BEAT.replace("bdrum:1/2", "cymbal+bdrum:1/2!", 1))
            else:
                perc.append(SIX_BEAT)
        parts = {
            "trumpets": "@0.95 " + melody,
            "horns": "@0.78 " + counter,
            "bones": "@0.82 " + join(six_stabs(bar) for bar in bars),
            "spiccato": "@0.68 " + join(six_arp(bar) for bar in bars),
            "celli": "@0.8 " + join(six_bass(bar, 28) for bar in bars),
            "basses": "@0.8 " + join(six_held(bar, 24) for bar in bars),
            "tuba": "@0.7 " + join(six_held(bar, 24) for bar in bars),
            "strings": "@0.5 " + join(six_pad(bar) for bar in bars),
            "perc": "@0.64 " + join(perc),
            "war": "@0.68 " + join([SIX_WAR] * (len(bars) - 1) + ["r:3"]),
            "timp": "@0.82 " + join(f"{name(root(bar[0], 40))}:1! r:2" for bar in bars[:-1]) + f" | {{{name(root(bars[-1][0], 40))}:1/4}}*10 {name(root(bars[-1][0], 40))}:1/2!",
            **thunder_danger(chords),
        }
        if winds:
            parts["winds"] = "@0.7 " + winds
        return parts

    chase_chords = "Em | C | Am | B7 | Em | C | Am D | G"
    chase_two_chords = "C | Am | Em | B7 | Em | C | Am B7 | B7"
    melody_one = ("B4:1/2! E5:1/2 G5:1/2 B5:1 A5:1/2 | G5:1/2 E5:1/2 C5:1/2 G5:1 E5:1/2 | "
                  "A5:1/2! C6:1/2 A5:1/2 E5:1 C5:1/2 | D#5:3/2! F#5:1/2 A5:1/2 F#5:1/2 | "
                  "B4:1/2! E5:1/2 G5:1/2 B5:1 A5:1/2 | G5:1/2 C6:1/2 E6:1/2 E6:1 D6:1/2 | "
                  "C6:1/2 A5:1/2 E5:1/2 D6:1 F#5:1/2 | G5:2~ B5:1")
    melody_two = ("C6:1! B5:1/2 A5:1 G5:1/2 | A5:1! G5:1/2 E5:1 C5:1/2 | "
                  "E5:1/2 G5:1/2 B5:1/2 E6:1 D6:1/2 | D#6:3/2! B5:1/2 F#5:1/2 A5:1/2 | "
                  "B4:1/2! E5:1/2 G5:1/2 B5:1 A5:1/2 | G5:1/2 C6:1/2 E6:1/2 G6:1 E6:1/2 | "
                  "C6:1/2 E6:1/2 G6:1/2 F#6:1 D#6:1/2 | B5:1! A5:1/2 F#5:1/2 D#5:1/2 B4:1/2")
    counter_one = "G4:3/2 E4:3/2 | E4:3/2 G4:3/2 | E4:3/2 A4:3/2 | F#4:3/2 D#4:3/2 | G4:3/2 B4:3/2 | G4:3/2 C5:3/2 | A4:3/2 A4:3/2 | B4:3/2 D5:3/2"
    counter_two = "E4:3/2 G4:3/2 | C4:3/2 E4:3/2 | G4:3/2 B4:3/2 | F#4:3/2 A4:3/2 | G4:3/2 E4:3/2 | C5:3/2 G4:3/2 | A4:3/2 F#4:3/2 | F#4:3/2 B4:3/2"
    winds_two = "r:3/2 E6:1/2 G6:1/2 B6:1/2 | r:3 | r:3/2 E6:1/2 G6:1/2 B6:1/2 | r:3 | r:3/2 E6:1/2 G6:1/2 B6:1/2 | r:3/2 C6:1/2 E6:1/2 G6:1/2 | r:3/2 F#6:1/2 A6:1/2 B6:1/2 | B6:1/2 A6:1/2 F#6:1/2 D#6:1/2 B5:1/2 F#5:1/2"
    chase_one = {"bars": 8, "chords": chase_chords, "parts": chase_part(melody_one, counter_one, chase_chords)}
    chase_two = {"bars": 8, "chords": chase_two_chords, "parts": chase_part(melody_two, counter_two, chase_two_chords, winds_two)}

    eye_chords = "G | D/F# | Em | C | Am | D | G C | D"
    bars = bars_of(eye_chords)
    eye = {
        "bars": 8, "key": "G major", "chords": eye_chords,
        "parts": {
            # The eye of the storm: the same opening leap, slowed down and turned to major.
            "violins": "@0.85 D5:1 G5:1/2 B5:3/2~ | A5:1 F#5:1/2 D5:3/2 | E5:1 G5:1/2 B5:1 E6:1/2 | E6:1 D6:1/2 C6:3/2 | C6:1 A5:1/2 E5:1 A5:1/2 | D6:1 C6:1/2 A5:3/2 | B5:1/2 D6:1/2 G6:1/2 E6:1 C6:1/2 | D6:3~",
            "winds": "@0.5 r:3 | r:3 | r:3 | r:3 | E6:3/2 A6:3/2 | F#6:3/2 D6:3/2 | r:3 | A6:3/2 F#6:3/2",
            "horns": "@0.58 B3:3/2 D4:3/2 | A3:3/2 D4:3/2 | B3:3/2 E4:3/2 | C4:3/2 E4:3/2 | C4:3/2 E4:3/2 | D4:3/2 F#4:3/2 | D4:3/2 E4:3/2 | D4:3/2 F#4:3/2",
            "harp": "@0.62 " + join(six_arp(bar, 55) for bar in bars),
            "strings": "@0.58 " + join(six_pad(bar) for bar in bars),
            "choir": "@0.55 " + join(six_pad(bar, 60) for bar in bars),
            "celli": "@0.6 " + join(six_held(bar, 36) for bar in bars),
            "basses": "@0.58 " + join(six_held(bar, 24) for bar in bars),
            "bells": "@0.46 D7:3/2 r:3/2 | D7:3/2 r:3/2 | B6:3/2 r:3/2 | C7:3/2 r:3/2 | C7:3/2 r:3/2 | A6:3/2 r:3/2 | B6:3/2 r:3/2 | A6:3/2 r:3/2",
            "timp": "@0.5 G2:1 r:2 | r:3 | E3:1 r:2 | C3:1 r:2 | A2:1 r:2 | D3:1 r:2 | G2:1 r:1/2 C3:1 r:1/2 | {D3:1/4}*12",
            "perc": "@0.5 cymbal:1 r:2 | r:3 | bdrum:1 r:2 | r:3 | bdrum:1 r:2 | r:3 | bdrum:1 r:2 | swell:3",
            "x_tremolo": "@0.36 " + join(six_tremolo(bar) for bar in bars),
        },
    }

    ambush_chords = "Em | F | Em | F | Dm Am | Bb F | Em F | B7"
    bars = bars_of(ambush_chords)
    ambush = {
        "bars": 8, "chords": ambush_chords, "key": "E phrygian",
        "parts": {
            "bones": "@0.92 E3:1/2! E3:1/2 E3:1/2 G3:1 F3:1/2 | F3:1/2! F3:1/2 F3:1/2 A3:1 C4:1/2 | E3:1/2! E3:1/2 E3:1/2 G3:1 F3:1/2 | F3:1/2! F3:1/2 F3:1/2 C4:1 A3:1/2 | D3:1/2! F3:1/2 A3:1/2 E3:1/2! A3:1/2 C4:1/2 | D3:1/2! F3:1/2 Bb3:1/2 C3:1/2! F3:1/2 A3:1/2 | B2:1/2! E3:1/2 G3:1/2 C3:1/2! F3:1/2 A3:1/2 | B2:1 D#3:1/2 F#3:1 A3:1/2",
            "trumpets": "@0.88 r:3/2 G4+B4+E5:1/2! r:1 | r:3/2 A4+C5+F5:1/2! r:1 | r:3/2 G4+B4+E5:1/2! r:1 | A4+C5+F5:1/2! r:1/2 A4+C5+F5:1/2! A4+C5+F5:3/2- | F4+A4+D5:3/2 E4+A4+C5:3/2 | F4+Bb4+D5:3/2 F4+A4+C5:3/2 | E4+G4+B4:3/2 F4+A4+C5:3/2 | D#4+F#4+B4:1/2! r:1/2 D#4+F#4+B4:1/2! F#4+A4+D#5:3/2-",
            "horns": "@0.8 E4:3 | F4:3 | E4:3 | F4:3 | D4:3/2 E4:3/2 | D4:3/2 C4:3/2 | B3:3/2 C4:3/2 | B3:3",
            "spiccato": "@0.72 " + join(six_gallop(bar) for bar in bars),
            "celli": "@0.82 " + join(six_bass(bar, 28) for bar in bars),
            "basses": "@0.82 " + join(six_held(bar, 24) for bar in bars),
            "tuba": "@0.75 " + join(six_held(bar, 24) for bar in bars),
            "choir": "@0.6 " + join(six_pad(bar, 60) for bar in bars),
            "timp": "@0.85 E3:1! r:2 | F3:1! r:2 | E3:1! r:2 | F3:1! r:2 | D3:1! r:1/2 A2:1! r:1/2 | Bb2:1! r:1/2 F3:1! r:1/2 | E3:1! r:1/2 F3:1! r:1/2 | {B2:1/4}*10 B2:1/2!",
            "perc": "@0.7 " + join([SIX_BEAT.replace("bdrum:1/2", "cymbal+bdrum:1/2!", 1)] + [SIX_BEAT] * 6 + [SIX_FILL]),
            "war": "@0.78 " + join([SIX_WAR] * 7 + ["{taiko:1/2}*6"]),
            **thunder_danger(ambush_chords),
        },
    }

    last_chords = "Em | C | Am | B7"
    last = {
        "bars": 4, "chords": last_chords,
        "parts": {
            "trumpets": "@0.98 E5+G5+B5:1/2! r:1/2 E5+G5+B5:1/2! G5+B5+E6:3/2- | E5+G5+C6:1/2! r:1/2 E5+G5+C6:1/2! G5+C6+E6:3/2- | E5+A5+C6:1/2! r:1/2 E5+A5+C6:1/2! A5+C6+E6:3/2- | D#5+F#5+B5:1/2! r:1/2 D#5+F#5+B5:1/2! F#5+A5+D#6:3/2-",
            "horns": "@0.85 E4+B4:3 | E4+G4:3 | E4+A4:3 | D#4+A4:3",
            "bones": "@0.9 E3+B3:1/2! r:1 E3+B3:1/2! r:1 | C3+G3:1/2! r:1 C3+G3:1/2! r:1 | A2+E3:1/2! r:1 A2+E3:1/2! r:1 | B2+F#3:1/2! r:1 B2+A3:1/2! r:1",
            "violins": "@0.8 E6:1/2 G6:1/2 B6:1/2 E7:3/2 | C6:1/2 E6:1/2 G6:1/2 C7:3/2 | C6:1/2 E6:1/2 A6:1/2 C7:3/2 | B5:1/2 D#6:1/2 F#6:1/2 B6:3/2",
            "spiccato": "@0.72 " + join(six_arp(bar) for bar in bars_of(last_chords)),
            "celli": "@0.84 " + join(six_bass(bar, 28) for bar in bars_of(last_chords)),
            "basses": "@0.84 " + join(six_held(bar, 24) for bar in bars_of(last_chords)),
            "tuba": "@0.8 E1:3 | C2:3 | A1:3 | B1:3",
            "choir": "@0.62 " + join(six_pad(bar, 60) for bar in bars_of(last_chords)),
            "timp": "@0.92 E3:1! r:2 | C3:1! r:2 | A2:1! r:2 | {B2:1/4}*10 B2:1/2!",
            "perc": "@0.76 " + join([SIX_BEAT.replace("bdrum:1/2", "cymbal+bdrum:1/2!", 1), SIX_BEAT, SIX_BEAT, SIX_FILL]),
            "war": "@0.8 " + join([SIX_WAR, SIX_WAR, SIX_WAR, "{taiko:1/2}*6"]),
            **thunder_danger(last_chords),
        },
    }

    return {
        "title": "Gauntlet of Thunderheads", "bpm": 186, "meter": "6/8", "key": "E minor", "loop_from": 1,
        "voices": voices,
        "sections": {"gather": gather, "hunt": hunt, "chase_one": chase_one, "chase_two": chase_two, "eye": eye,
                     "ambush": ambush, "last": last},
        "arrangement": ["gather", "hunt", "chase_one", "chase_two", "eye", "ambush", "chase_one", "chase_two", "last"],
    }


# ---- Defeat: a one-shot, the falling answer to the victory fanfare. ----

def defeat():
    return {
        "title": "Defeat Lament", "bpm": 72, "meter": "4/4", "key": "C minor", "loop": False,
        "voices": {
            "horns": voice("orch_horns", 1.1, -0.2),
            "bones": voice("orch_trombones", 0.8, 0.2),
            "strings": voice("orch_strings", 1.1),
            "celli": voice("orch_celli", 0.8, -0.15),
            "basses": voice("orch_basses", 0.8),
            "choir": voice("orch_choir", 0.9),
            "timp": voice("timpani", 0.6),
            "perc": voice("drums", 0.65),
        },
        "sections": {"fall": {
            "bars": 3, "chords": "Cm | Ab Fm | Cm",
            "parts": {
                "horns": "@0.85 G4:3/2! Eb4:1/2 C4:2 | C4:1 Ab3:1 F3:1/2 Ab3:1/2 D4:1 | C4:4-",
                "bones": "@0.7 r:4 | Ab2+Eb3:2 F2+C3:2 | C2+G2:4-",
                "strings": "@0.6 C4+Eb4+G4:4 | Ab3+C4+Eb4:2 F3+Ab3+C4:2 | C3+G3+Eb4:4",
                "celli": "@0.7 C3:4 | Ab2:2 F2:2 | C2:4",
                "basses": "@0.7 C2:4 | Ab1:2 F1:2 | C1:4",
                "choir": "@0.55 Eb4+G4:4 | Eb4+Ab4:2 C4+F4:2 | Eb4+G4:4",
                "timp": "@0.8 C3:1! r:3 | Ab2:1 r:1 F2:1 r:1 | {C3:1/4}*4 C3:1! r:2",
                "perc": "@0.8 gong:1 r:3 | r:4 | bdrum:1 r:3",
            },
        }},
        "arrangement": ["fall"],
    }


def main():
    for slug, song in (("wings_of_the_tempest", tempest()), ("gauntlet_of_thunderheads", thunderheads()), ("defeat_lament", defeat())):
        (HERE / f"{slug}.json").write_text(json.dumps(song, indent=2) + "\n", encoding="utf-8")
        print("wrote", slug)


if __name__ == "__main__":
    main()
