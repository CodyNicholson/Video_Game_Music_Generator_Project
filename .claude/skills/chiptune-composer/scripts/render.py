#!/usr/bin/env python3
"""Render a chiptune song file to game-ready audio.

    render.py song.json --out output              full render
    render.py song.json --check                   validate and lint only
    render.py song.json --section B --out output  audition one section
    render.py song.json --out output --preview    also write intro + loop x2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import output  # noqa: E402
import score  # noqa: E402
import synth  # noqa: E402

TAIL_SECONDS = 2.4
TARGET_PEAK = 0.891  # -1 dBFS leaves headroom for lossy encoding in game engines.
HUMANIZE_SECONDS = 0.0025


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "song"


def _render_events(events, voices, sr, length, cache, title):
    """Mix events into one dry stereo buffer per voice."""
    buffers = {name: np.zeros((length, 2), dtype=np.float32) for name in voices}
    jitter = np.random.default_rng(synth.stable_seed("humanize", title))
    params_by_voice = {}
    for name, voice in voices.items():
        if voice.get("instrument") != "drums":
            params_by_voice[name] = synth.resolve_params(voice)
    for event in events:
        voice = voices[event.voice]
        is_drums = voice.get("instrument") == "drums"
        duration = event.end_s - event.start_s
        velocity = round(event.velocity, 3)
        key = (event.voice, event.pitch, round(duration, 3), velocity, event.mods)
        note = cache.get(key)
        if note is None:
            seed = synth.stable_seed(title, *key)
            if is_drums:
                note = synth.render_drum(event.pitch, duration, velocity, event.mods, sr, seed)
            else:
                note = synth.render_note(params_by_voice[event.voice], event.pitch, duration, velocity, event.mods, sr, seed)
            note = note.astype(np.float32)
            cache[key] = note
        # A section drifts slightly but drums hold the grid, as a real band does.
        offset = 0.0 if is_drums else float(jitter.uniform(-HUMANIZE_SECONDS, HUMANIZE_SECONDS))
        start = max(int(round((event.start_s + offset) * sr)), 0)
        end = min(start + note.shape[0], length)
        if end > start:
            buffers[event.voice][start:end] += note[: end - start]
    return buffers


def _apply_voice_settings(buffers, voices, bpm, sr, ir):
    """Pan, gain, echo and reverb each voice, returning wet buffers per layer."""
    length = next(iter(buffers.values())).shape[0]
    layers = {}
    sends = {}
    levels = {}
    for name, dry in buffers.items():
        voice = voices[name]
        pan = float(voice.get("pan", 0.0))
        gain = float(voice.get("gain", 1.0))
        angle = (pan + 1.0) * np.pi / 4.0
        pan_gains = np.array([np.cos(angle), np.sin(angle)], dtype=np.float32) * np.sqrt(2.0)
        signal = dry * pan_gains * gain

        echo = float(voice.get("echo", 0.0))
        if echo:
            # Dotted-eighth ping-pong, the classic way to widen a single chip channel.
            delay = int(0.75 * 60.0 / bpm * sr)
            source = signal.copy()
            for tap in range(1, 4):
                shift = delay * tap
                if shift >= length:
                    break
                side = (tap + 1) % 2
                level = echo * (0.55 ** (tap - 1))
                signal[shift:, side] += source[: length - shift].mean(axis=1) * level

        rms = float(np.sqrt(np.mean(signal ** 2)))
        levels[name] = rms
        layer = voice.get("layer", "base")
        layers.setdefault(layer, np.zeros((length, 2), dtype=np.float32))
        layers[layer] += signal
        if voice.get("instrument") == "drums":
            default_send = 0.1
        else:
            default_send = synth.resolve_params(voice)["reverb"]
        send = float(voice.get("reverb", default_send))
        if send:
            sends.setdefault(layer, np.zeros((length, 2), dtype=np.float32))
            sends[layer] += signal * send

    tail = ir.shape[0]
    out = {}
    for layer, signal in layers.items():
        padded = np.zeros((length + tail, 2), dtype=np.float32)
        padded[:length] = signal
        if layer in sends:
            wet = synth.convolve_stereo(sends[layer], ir)
            padded[: wet.shape[0]] += wet * 0.9
        out[layer] = padded
    return out, levels


def _wrap_loop(signal, loop_len):
    """Fold everything past the loop end back to its start, including note releases
    and reverb, so the last sample flows into the first with no gap or click."""
    wrapped = signal[:loop_len].copy()
    position = loop_len
    while position < signal.shape[0]:
        size = min(loop_len, signal.shape[0] - position)
        wrapped[:size] += signal[position:position + size]
        position += size
    return wrapped


def _saturate(signal):
    """Gentle glue on each layer. It runs after loop wrapping so the seam stays exact,
    and per layer so a mix is still the exact sum of its stems."""
    return np.tanh(signal * 0.72) / 0.72


def _fade_tail(signal, sr, seconds=0.012):
    n = min(int(seconds * sr), signal.shape[0])
    if n > 0:
        signal[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)[:, None]
    return signal


def render_song(song, sr=44100, only_section=None):
    """Compile and render, returning the layers plus all timing metadata."""
    compiled = score.compile_song(song, synth.INSTRUMENTS, synth.DRUM_NAMES, only_section)
    for voice in compiled.voices.values():
        if voice.get("instrument") != "drums":
            synth.resolve_params(voice)
    ir = synth.impulse_response(sr)
    segments = compiled.segments
    total_s = segments[-1].end_s
    cache = {}

    if compiled.loops:
        boundary_s = segments[compiled.loop_from].start_s
    else:
        boundary_s = 0.0

    intro_len = int(round(boundary_s * sr))
    body_len = int(round((total_s - boundary_s) * sr))
    pad = int(TAIL_SECONDS * sr)

    def render_part(events, start_s, length):
        moved = [_shifted(event, start_s) for event in events]
        buffers = _render_events(moved, compiled.voices, sr, length, cache, compiled.title)
        return _apply_voice_settings(buffers, compiled.voices, compiled.bpm, sr, ir)

    intro_events = [e for e in compiled.events if compiled.loops and e.segment < compiled.loop_from]
    body_events = [e for e in compiled.events if not compiled.loops or e.segment >= compiled.loop_from]

    body_layers, levels = render_part(body_events, boundary_s, body_len + pad)
    if compiled.loops:
        layers = {name: _saturate(_wrap_loop(signal, body_len)) for name, signal in body_layers.items()}
    else:
        layers = {name: _fade_tail(_saturate(signal[: body_len + pad]), sr, 0.25) for name, signal in body_layers.items()}

    if intro_len:
        intro_layers, _ = render_part(intro_events, 0.0, intro_len + pad)
        joined = {}
        for name in set(layers) | set(intro_layers):
            body_part = layers.get(name)
            if body_part is None:
                body_part = np.zeros((next(iter(layers.values())).shape[0], 2), dtype=np.float32)
            intro_part = intro_layers.get(name)
            head = np.zeros((intro_len, 2), dtype=np.float32)
            if intro_part is not None:
                head = _fade_tail(_saturate(intro_part[:intro_len]), sr)
            joined[name] = np.concatenate((head, body_part))
        layers = joined

    mix = sum(layers.values())
    peak = max(float(np.max(np.abs(mix))), *(float(np.max(np.abs(s))) for s in layers.values()), 1e-6)
    gain = TARGET_PEAK / peak
    layers = {name: (signal * gain).astype(np.float32) for name, signal in layers.items()}
    mix = sum(layers.values())

    loop_range = (intro_len, intro_len + body_len) if compiled.loops else None
    return {
        "compiled": compiled, "layers": layers, "mix": mix, "loop": loop_range,
        "voice_levels": {name: level * gain for name, level in levels.items()},
        "sample_rate": sr,
    }


def _shifted(event, start_s):
    return score.Event(event.voice, event.pitch, event.start_s - start_s, event.end_s - start_s,
                       event.start_beat, event.end_beat, event.velocity, event.mods, event.segment)


def _db(value):
    return 20.0 * np.log10(max(value, 1e-9))


def _band_balance(mix, sr):
    """Energy per band relative to the loudest band, to catch a boomy or harsh mix."""
    spectrum = np.abs(np.fft.rfft(mix.mean(axis=1))) ** 2
    freqs = np.fft.rfftfreq(mix.shape[0], 1.0 / sr)
    bands = {"sub_20_80": (20, 80), "bass_80_250": (80, 250), "mid_250_2k": (250, 2000),
             "presence_2k_6k": (2000, 6000), "air_6k_16k": (6000, 16000)}
    energy = {name: float(spectrum[(freqs >= low) & (freqs < high)].sum()) for name, (low, high) in bands.items()}
    top = max(energy.values()) or 1.0
    return {name: round(10.0 * np.log10(max(value, 1e-12) / top), 1) for name, value in energy.items()}


def analyze(result):
    """Numbers that stand in for listening: loudness, balance, clipping and the seam."""
    mix = result["mix"]
    sr = result["sample_rate"]
    report = {
        "duration_seconds": round(mix.shape[0] / sr, 3),
        "peak_dbfs": round(_db(float(np.max(np.abs(mix)))), 2),
        "rms_dbfs": round(_db(float(np.sqrt(np.mean(mix ** 2)))), 2),
        "clipped_samples": int(np.sum(np.abs(mix) >= 0.9999)),
        "voice_rms_dbfs": {name: round(_db(level), 1) for name, level in result["voice_levels"].items()},
        "band_balance_db": _band_balance(mix, sr),
        "sections": [],
    }
    for segment in result["compiled"].segments:
        begin = int(segment.start_s * sr)
        end = min(int(segment.end_s * sr), mix.shape[0])
        chunk = mix[begin:end]
        report["sections"].append({
            "name": segment.name, "start_seconds": round(segment.start_s, 3), "end_seconds": round(segment.end_s, 3),
            "transpose": segment.transpose, "rms_dbfs": round(_db(float(np.sqrt(np.mean(chunk ** 2)))), 1) if len(chunk) else None,
        })
    if result["loop"]:
        start, end = result["loop"]
        seam_jump = float(np.max(np.abs(mix[end - 1] - mix[start])))
        typical = float(np.percentile(np.abs(np.diff(mix[start:end], axis=0)), 99.9))
        report["loop_seam_jump"] = round(seam_jump, 5)
        report["loop_seam_typical_step_p99_9"] = round(typical, 5)
        report["loop_seam_ok"] = seam_jump <= max(typical * 1.5, 0.02)
    return report


def write_outputs(result, out_dir, slug, preview=False, spectrogram=True, midi=True):
    out_dir = Path(out_dir) / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    sr = result["sample_rate"]
    mix = result["mix"]
    written = []

    def record(path):
        written.append(str(path))
        return path

    output.write_wav(record(out_dir / f"{slug}.wav"), mix, sr, result["loop"])
    layers = result["layers"]
    if len(layers) > 1:
        for name, signal in sorted(layers.items()):
            output.write_wav(record(out_dir / f"{slug}_stem_{slugify(name)}.wav"), signal, sr, result["loop"])
    if midi:
        output.write_midi(record(out_dir / f"{slug}.mid"), result["compiled"])
    if spectrogram:
        output.write_spectrogram_png(record(out_dir / f"{slug}_spectrogram.png"), mix, sr)
    if preview and result["loop"]:
        start, end = result["loop"]
        audition = np.concatenate((mix[:end], mix[start:end]))
        output.write_wav(record(out_dir / f"{slug}_loop_preview.wav"), audition, sr)

    report = analyze(result)
    meta = {
        "title": result["compiled"].title,
        "sample_rate": sr,
        "loop_start_sample": result["loop"][0] if result["loop"] else None,
        "loop_end_sample": result["loop"][1] if result["loop"] else None,
        "layers": sorted(layers),
        **report,
    }
    meta_path = record(out_dir / f"{slug}.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return written, meta


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a chiptune song file.")
    parser.add_argument("song", type=Path)
    parser.add_argument("--out", default="output", help="output folder (default: output)")
    parser.add_argument("--check", action="store_true", help="validate and lint without rendering")
    parser.add_argument("--section", help="render only this section, for quick auditioning")
    parser.add_argument("--preview", action="store_true", help="also write a file that plays the loop twice")
    parser.add_argument("--sample-rate", type=int, default=44100)
    args = parser.parse_args(argv)

    try:
        song = json.loads(args.song.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"ERROR: cannot read {args.song}: {err}", file=sys.stderr)
        return 2

    try:
        compiled = score.compile_song(song, synth.INSTRUMENTS, synth.DRUM_NAMES, args.section)
        warnings = score.lint(song, synth.INSTRUMENTS, synth.DRUM_NAMES)
        for voice in compiled.voices.values():
            if voice.get("instrument") != "drums":
                synth.resolve_params(voice)
    except score.SongError as err:
        print(f"{len(err.problems)} error(s):", file=sys.stderr)
        for problem in err.problems:
            print(f"  ERROR: {problem}", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"  warning: {warning}")
    print(f"{compiled.title}: {compiled.segments[-1].end_s:.1f}s, {len(compiled.events)} notes, {len(warnings)} warning(s)")
    if args.check:
        return 0

    result = render_song(song, args.sample_rate, args.section)
    slug = slugify(args.song.stem)
    if args.section:
        slug = f"{slug}__{slugify(args.section)}"
    written, meta = write_outputs(result, args.out, slug, args.preview)
    print(f"peak {meta['peak_dbfs']} dBFS, rms {meta['rms_dbfs']} dBFS, clipped samples {meta['clipped_samples']}")
    print("voice rms dBFS: " + ", ".join(f"{k} {v}" for k, v in meta["voice_rms_dbfs"].items()))
    print("band balance dB: " + ", ".join(f"{k} {v}" for k, v in meta["band_balance_db"].items()))
    print("sections rms: " + ", ".join(f"{s['name']} {s['rms_dbfs']}" for s in meta["sections"]))
    if result["loop"]:
        print(f"loop samples {result['loop'][0]}..{result['loop'][1]}, seam ok: {meta['loop_seam_ok']} (jump {meta['loop_seam_jump']})")
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
