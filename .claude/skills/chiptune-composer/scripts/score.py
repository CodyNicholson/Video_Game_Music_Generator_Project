"""Parse, validate and lint chiptune song files. Standard library only.

A song is a JSON document (see references/song-format.md). This module turns it
into a flat, timed list of note events and reports musical mistakes the author
cannot hear: wrong bar lengths, unknown names, out-of-range notes, and clashes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PITCH_RE = re.compile(r"^([A-Ga-g])(#|b)?(-?\d)$")
TOKEN_RE = re.compile(r"^([A-Za-z0-9#_+]+):(\d+(?:\.\d+)?(?:/\d+)?)([!.\-^v~&]*)$")
VEL_RE = re.compile(r"^@(\d*\.?\d+)$")

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    # Natural, harmonic and melodic minor tones are all treated as in-key.
    "minor": [0, 2, 3, 5, 7, 8, 9, 10, 11],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
}

CHORD_QUALITIES = {
    "": [0, 4, 7],
    "maj": [0, 4, 7],
    "m": [0, 3, 7],
    "min": [0, 3, 7],
    "5": [0, 7],
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "9": [0, 2, 4, 7, 10],
    "m9": [0, 2, 3, 7, 10],
    "maj9": [0, 2, 4, 7, 11],
    "add9": [0, 2, 4, 7],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "7sus4": [0, 5, 7, 10],
    "dim": [0, 3, 6],
    "dim7": [0, 3, 6, 9],
    "m7b5": [0, 3, 6, 10],
    "aug": [0, 4, 8],
}
CHORD_RE = re.compile(r"^([A-G])(#|b)?([a-z0-9]*)(?:/([A-G])(#|b)?)?$")


class SongError(ValueError):
    """Raised with every problem found, so one run can fix them all at once."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class Event:
    voice: str
    pitch: object  # MIDI number, or drum name for drum voices
    start_s: float
    end_s: float
    start_beat: float
    end_beat: float
    velocity: float
    mods: str
    segment: int


@dataclass(frozen=True)
class Segment:
    name: str
    index: int
    start_s: float
    end_s: float
    start_beat: float
    end_beat: float
    bpm: float
    meter: str
    transpose: int


@dataclass(frozen=True)
class Compiled:
    title: str
    events: tuple
    segments: tuple
    loop_from: int  # segment index where the loop begins
    loops: bool
    voices: dict
    bpm: float


@dataclass(frozen=True)
class _Tok:
    start: Fraction
    dur: Fraction
    pitches: tuple
    velocity: float
    mods: str


def parse_pitch(text):
    match = PITCH_RE.match(text)
    if not match:
        raise ValueError(f"not a pitch: {text!r}")
    letter, accidental, octave = match.groups()
    value = NOTE_OFFSETS[letter.upper()] + 12 * (int(octave) + 1)
    return value + {"#": 1, "b": -1, None: 0}[accidental]


def meter_beats(meter):
    """Bar length in quarter notes. Durations are always written in quarters."""
    try:
        top, bottom = str(meter).split("/")
        beats = Fraction(int(top) * 4, int(bottom))
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"bad meter {meter!r}; use a form like '4/4' or '6/8'") from None
    if beats <= 0:
        raise ValueError(f"bad meter {meter!r}")
    return beats


def _expand_repeats(text):
    """Expand `{ ... }*N` groups, which may nest, into a flat token list."""
    spaced = text.replace("{", " { ").replace("}", " }")
    stack = [[]]
    for token in spaced.split():
        if token == "{":
            stack.append([])
        elif token.startswith("}"):
            if len(stack) == 1:
                raise ValueError("'}' without a matching '{'")
            count_text = token[2:] if token.startswith("}*") else None
            if token != "}" and not (count_text and count_text.isdigit()):
                raise ValueError(f"bad repeat {token!r}; write it as }}*N")
            count = int(count_text) if count_text else 2
            group = stack.pop()
            stack[-1].extend(group * count)
        else:
            stack[-1].append(token)
    if len(stack) != 1:
        raise ValueError("'{' without a matching '}'")
    return stack[0]


def parse_part(text, bar_len, bars, is_drums, drum_names=()):
    """Parse one voice's text into tokens, checking every bar adds up exactly.

    Exact fractions are used so 1/3 + 1/3 + 1/3 == 1 and a typed 0.33 is caught
    as an error, which is what keeps every voice aligned over a long section.
    """
    tokens = []
    position = Fraction(0)
    bar_start = Fraction(0)
    bar_number = 1
    velocity = 0.8
    saw_barline = False
    for raw in _expand_repeats(text):
        if raw == "|":
            saw_barline = True
            length = position - bar_start
            if length != bar_len:
                raise ValueError(f"bar {bar_number} has {_fmt(length)} beats, expected {_fmt(bar_len)}")
            bar_start = position
            bar_number += 1
            continue
        vel_match = VEL_RE.match(raw)
        if vel_match:
            velocity = float(vel_match.group(1))
            if not 0 <= velocity <= 1:
                raise ValueError(f"velocity {raw!r} must be between 0 and 1")
            continue
        match = TOKEN_RE.match(raw)
        if not match:
            raise ValueError(f"bad token {raw!r} in bar {bar_number}; expected like D5:1/2 or r:1")
        names, dur_text, mods = match.groups()
        duration = Fraction(dur_text)
        if duration <= 0:
            raise ValueError(f"zero-length token {raw!r} in bar {bar_number}")
        pitches = []
        if names != "r":
            for name in names.split("+"):
                if is_drums:
                    if name not in drum_names:
                        raise ValueError(f"unknown drum {name!r} in bar {bar_number}; available: {', '.join(sorted(drum_names))}")
                    pitches.append(name)
                else:
                    try:
                        pitches.append(parse_pitch(name))
                    except ValueError:
                        raise ValueError(f"bad pitch {name!r} in {raw!r}, bar {bar_number}") from None
        tokens.append(_Tok(position, duration, tuple(pitches), velocity, mods))
        position += duration

    end_length = position - bar_start
    if end_length and saw_barline and end_length != bar_len:
        raise ValueError(f"bar {bar_number} has {_fmt(end_length)} beats, expected {_fmt(bar_len)}")
    expected = bar_len * bars
    if position != expected:
        raise ValueError(f"total is {_fmt(position)} beats, expected {_fmt(expected)} ({bars} bars)")
    return _merge_ties(tokens)


def _merge_ties(tokens):
    merged = []
    for token in tokens:
        if merged and "&" in merged[-1].mods:
            previous = merged[-1]
            if not token.pitches or token.pitches != previous.pitches:
                raise ValueError(f"tie '&' at beat {_fmt(previous.start)} must lead into the same pitch")
            mods = previous.mods.replace("&", "") + token.mods
            merged[-1] = _Tok(previous.start, previous.dur + token.dur, previous.pitches, previous.velocity, mods)
        else:
            merged.append(token)
    if merged and "&" in merged[-1].mods:
        raise ValueError("the last note ties '&' into nothing")
    return merged


def _fmt(value):
    return str(float(value)) if Fraction(value).denominator in (1, 2, 4, 8, 16) else str(value)


def _swung(beat, swing):
    """Delay off-beat eighths. `swing` is where the off-beat lands (0.5 = straight)."""
    if not swing or swing == 0.5:
        return float(beat)
    whole = int(beat)
    frac = float(beat) - whole
    if frac <= 0.5:
        return whole + frac * (swing / 0.5)
    return whole + swing + (frac - 0.5) * ((1 - swing) / 0.5)


def compile_song(song, instruments, drum_names, only_section=None):
    """Return a Compiled song, or raise SongError listing every problem."""
    problems = []
    title = song.get("title", "Untitled")
    voices = song.get("voices") or {}
    sections = song.get("sections") or {}
    arrangement = song.get("arrangement") or []
    if not voices:
        problems.append("song has no 'voices'")
    if not sections:
        problems.append("song has no 'sections'")
    if not arrangement and not only_section:
        problems.append("song has no 'arrangement'")

    for name, voice in voices.items():
        instrument = voice.get("instrument")
        if instrument != "drums" and instrument not in instruments:
            problems.append(f"voice {name!r}: unknown instrument {instrument!r}; available: drums, {', '.join(sorted(instruments))}")

    try:
        song_bpm = float(song.get("bpm", 120))
        if song_bpm <= 0:
            raise ValueError
    except (TypeError, ValueError):
        problems.append("'bpm' must be a positive number")
        song_bpm = 120.0

    # Parse each section once; arrangement entries reuse the parsed notes.
    parsed = {}
    for section_name, section in sections.items():
        try:
            bar_len = meter_beats(section.get("meter", song.get("meter", "4/4")))
        except ValueError as err:
            problems.append(f"section {section_name!r}: {err}")
            continue
        bars = section.get("bars")
        if not isinstance(bars, int) or bars <= 0:
            problems.append(f"section {section_name!r}: 'bars' must be a positive whole number")
            continue
        parts = {}
        for voice_name, text in (section.get("parts") or {}).items():
            if voice_name not in voices:
                problems.append(f"section {section_name!r}: part for undefined voice {voice_name!r}")
                continue
            is_drums = voices[voice_name].get("instrument") == "drums"
            try:
                parts[voice_name] = parse_part(text, bar_len, bars, is_drums, drum_names)
            except ValueError as err:
                problems.append(f"section {section_name!r}, voice {voice_name!r}: {err}")
        parsed[section_name] = (bar_len, bars, parts)

    if only_section is not None:
        if only_section not in sections:
            problems.append(f"no section named {only_section!r}; have: {', '.join(sections)}")
        arrangement = [only_section]

    entries = []
    for position, item in enumerate(arrangement):
        spec = {"section": item} if isinstance(item, str) else dict(item)
        name = spec.get("section")
        if name not in sections:
            problems.append(f"arrangement[{position}]: unknown section {name!r}")
            continue
        entries.append((name, int(spec.get("transpose", 0))))

    loops = bool(song.get("loop", True)) and only_section is None
    loop_from = int(song.get("loop_from", 0)) if only_section is None else 0
    if loops and not 0 <= loop_from < max(len(entries), 1):
        problems.append(f"'loop_from' {loop_from} is outside the arrangement (0..{len(entries) - 1})")

    if problems:
        raise SongError(problems)

    events = []
    segments = []
    clock_s = 0.0
    clock_beat = 0.0
    for index, (name, transpose) in enumerate(entries):
        section = sections[name]
        bar_len, bars, parts = parsed[name]
        bpm = float(section.get("bpm", song_bpm))
        seconds_per_beat = 60.0 / bpm
        swing = float(section.get("swing", song.get("swing", 0)) or 0)
        length_beats = float(bar_len * bars)

        for voice_name, tokens in parts.items():
            voice = voices[voice_name]
            is_drums = voice.get("instrument") == "drums"
            voice_swing = swing if voice.get("swing", True) else 0
            shift = 0 if is_drums else transpose + 12 * int(voice.get("octave", 0))
            arp_step = voice.get("arp")
            for token in tokens:
                if not token.pitches:
                    continue
                for pitch, start, dur, mods in _voiced(token, arp_step):
                    begin = _swung(start, voice_swing)
                    finish = _swung(start + dur, voice_swing)
                    if finish <= begin:
                        finish = begin + float(dur)
                    events.append(Event(
                        voice=voice_name,
                        pitch=pitch if is_drums else pitch + shift,
                        start_s=clock_s + begin * seconds_per_beat,
                        end_s=clock_s + finish * seconds_per_beat,
                        start_beat=clock_beat + begin,
                        end_beat=clock_beat + finish,
                        velocity=token.velocity,
                        mods=mods,
                        segment=index,
                    ))

        length_s = length_beats * seconds_per_beat
        segments.append(Segment(
            name=name, index=index, start_s=clock_s, end_s=clock_s + length_s,
            start_beat=clock_beat, end_beat=clock_beat + length_beats, bpm=bpm,
            meter=str(section.get("meter", song.get("meter", "4/4"))), transpose=transpose,
        ))
        clock_s += length_s
        clock_beat += length_beats

    events.sort(key=lambda e: (e.start_s, e.voice))
    return Compiled(title, tuple(events), tuple(segments), loop_from, loops, voices, song_bpm)


def _voiced(token, arp_step):
    """Yield sounding notes for a token, spreading chords when the voice arpeggiates."""
    if arp_step and len(token.pitches) > 1:
        step = Fraction(str(arp_step))
        ordered = sorted(token.pitches)
        position = token.start
        end = token.start + token.dur
        cursor = 0
        while position < end:
            length = min(step, end - position)
            # Keep only the accent on arpeggio notes: scoops on every step would smear.
            mods = "!" if ("!" in token.mods and cursor == 0) else "-"
            yield ordered[cursor % len(ordered)], position, length, mods
            position += length
            cursor += 1
        return
    for pitch in token.pitches:
        yield pitch, token.start, token.dur, token.mods


def parse_key(text):
    """'D major' -> (2, set of pitch classes). Raises ValueError on a bad key."""
    match = re.match(r"^([A-G])(#|b)?\s+(\w+)$", str(text).strip())
    if not match or match.group(3).lower() not in SCALES:
        raise ValueError(f"bad key {text!r}; use a form like 'D major' or 'E dorian'")
    tonic = (NOTE_OFFSETS[match.group(1)] + {"#": 1, "b": -1, None: 0}[match.group(2)]) % 12
    return tonic, {(tonic + degree) % 12 for degree in SCALES[match.group(3).lower()]}


def parse_chord(text):
    """'F#m7/A' -> set of pitch classes including the slash bass."""
    match = CHORD_RE.match(text)
    if not match or match.group(3) not in CHORD_QUALITIES:
        raise ValueError(f"unknown chord {text!r}")
    root = (NOTE_OFFSETS[match.group(1)] + {"#": 1, "b": -1, None: 0}[match.group(2)]) % 12
    tones = {(root + step) % 12 for step in CHORD_QUALITIES[match.group(3)]}
    bass = root
    if match.group(4):
        bass = (NOTE_OFFSETS[match.group(4)] + {"#": 1, "b": -1, None: 0}[match.group(5)]) % 12
        tones.add(bass)
    return tones, bass


def _chord_at(chords_text, bar_len):
    """Return a list of (start_beat, end_beat, tones, bass, label) for a section."""
    spans = []
    for bar_index, bar in enumerate(chords_text.split("|")):
        names = bar.split()
        if not names:
            continue
        width = bar_len / len(names)
        for slot, name in enumerate(names):
            tones, bass = parse_chord(name)
            begin = bar_len * bar_index + width * slot
            spans.append((float(begin), float(begin + width), tones, bass, name))
    return spans


def lint(song, instruments, drum_names):
    """Return warnings about likely musical mistakes. Warnings never block a render.

    These stand in for ears: chromatic notes and tense intervals are often
    deliberate, so each warning is something to look at, not necessarily to fix.
    """
    warnings = []
    voices = song.get("voices") or {}
    for section_name, section in (song.get("sections") or {}).items():
        meter = section.get("meter", song.get("meter", "4/4"))
        bar_len = meter_beats(meter)
        if str(meter).endswith("/8"):
            pulse = Fraction(3, 2)
        else:
            pulse = Fraction(1) if bar_len == 3 else Fraction(2)

        try:
            scale = parse_key(section.get("key", song["key"]))[1] if section.get("key", song.get("key")) else None
        except ValueError as err:
            warnings.append(f"section {section_name!r}: {err}")
            scale = None

        spans = []
        if section.get("chords"):
            try:
                spans = _chord_at(section["chords"], bar_len)
            except ValueError as err:
                warnings.append(f"section {section_name!r}: {err}")

        sounding = []
        for voice_name, text in (section.get("parts") or {}).items():
            voice = voices.get(voice_name) or {}
            instrument = voice.get("instrument")
            if instrument == "drums" or instrument not in instruments:
                continue
            tokens = parse_part(text, bar_len, section["bars"], False, drum_names)
            low, high = instruments[instrument].get("range", (0, 127))
            octave = 12 * int(voice.get("octave", 0))
            is_bass = instruments[instrument].get("role") == "bass"
            for token in tokens:
                for pitch in token.pitches:
                    where = _where(section_name, voice_name, token.start, bar_len)
                    if not low <= pitch + octave <= high:
                        warnings.append(f"{where}: {_name(pitch + octave)} is outside {instrument}'s range ({_name(low)}-{_name(high)})")
                    strong = token.start % pulse == 0
                    chord = next((s for s in spans if s[0] <= float(token.start) < s[1]), None)
                    in_chord = chord is None or pitch % 12 in chord[2]
                    in_scale = scale is None or pitch % 12 in scale
                    if is_bass and chord and float(token.start) == chord[0] and pitch % 12 != chord[3]:
                        warnings.append(f"{where}: bass plays {_name(pitch)} at the change to {chord[4]}, whose bass note differs")
                    elif strong and token.dur >= 1 and not in_chord and not in_scale:
                        warnings.append(f"{where}: long {_name(pitch)} on a strong beat fits neither the chord nor the key")
                    if not voice.get("arp"):
                        sounding.append((token.start, token.start + token.dur, pitch + octave, voice_name))

        reported = 0
        for i, (start_a, end_a, pitch_a, voice_a) in enumerate(sounding):
            if start_a % pulse != 0:
                continue
            for start_b, end_b, pitch_b, voice_b in sounding[i + 1:]:
                if voice_a == voice_b or abs(pitch_a - pitch_b) not in (1, 13):
                    continue
                overlap = min(end_a, end_b) - max(start_a, start_b)
                if overlap >= 1 and start_b % pulse == 0 and start_a == start_b:
                    if reported < 8:
                        where = _where(section_name, voice_a, start_a, bar_len)
                        warnings.append(f"{where}: {_name(pitch_a)} clashes with {_name(pitch_b)} in {voice_b} for {_fmt(overlap)} beats")
                    reported += 1
        if reported > 8:
            warnings.append(f"section {section_name!r}: {reported - 8} more clashes not shown")
    return warnings


def _where(section, voice, start, bar_len):
    bar = int(start // bar_len) + 1
    beat = float(start % bar_len) + 1
    return f"section {section!r}, {voice}, bar {bar} beat {beat:g}"


def _name(midi):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"
