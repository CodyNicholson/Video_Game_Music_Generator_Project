"""Self-written file writers: WAV with loop points, Standard MIDI and PNG."""

from __future__ import annotations

import struct
import zlib

import numpy as np

from synth import DRUM_MIDI, INSTRUMENTS


def write_wav(path, stereo, sr, loop=None):
    """Write 16-bit stereo PCM. `loop` adds a `smpl` chunk that samplers and engines read."""
    pcm = (np.clip(stereo, -1.0, 1.0) * 32767.0).round().astype("<i2")
    data = pcm.tobytes()
    fmt = struct.pack("<HHIIHH", 1, 2, sr, sr * 4, 4, 16)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if loop is not None:
        start, end = loop
        # smpl header (36 bytes) then one 24-byte loop; the end point is inclusive.
        smpl = struct.pack("<9I", 0, 0, int(1e9 / sr), 60, 0, 0, 0, 1, 0)
        smpl += struct.pack("<6I", 0, 0, int(start), int(end) - 1, 0, 0)
        chunks += b"smpl" + struct.pack("<I", len(smpl)) + smpl
    chunks += b"data" + struct.pack("<I", len(data)) + data
    with open(path, "wb") as handle:
        handle.write(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)


def _varlen(value):
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def _track(events):
    """events: (tick, sort_order, raw_bytes). Note-offs sort first at equal ticks."""
    body = bytearray()
    last = 0
    for tick, _, raw in sorted(events, key=lambda item: (item[0], item[1])):
        body += _varlen(tick - last) + raw
        last = tick
    body += _varlen(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def write_midi(path, compiled, ppq=480):
    """Export the arrangement as editable MIDI so a person can rework it in any DAW."""
    tick = lambda beat: int(round(beat * ppq))
    conductor = []
    title = compiled.title.encode("utf-8", "replace")[:120]
    conductor.append((0, 0, b"\xff\x03" + _varlen(len(title)) + title))
    last_meter = None
    for segment in compiled.segments:
        micros = int(round(60_000_000 / segment.bpm))
        at = tick(segment.start_beat)
        conductor.append((at, 1, b"\xff\x51\x03" + micros.to_bytes(3, "big")))
        if segment.meter != last_meter:
            top, bottom = (int(part) for part in segment.meter.split("/"))
            power = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}.get(bottom, 2)
            conductor.append((at, 1, b"\xff\x58\x04" + bytes([top, power, 24, 8])))
            last_meter = segment.meter
        name = segment.name.encode("utf-8", "replace")[:60]
        conductor.append((at, 2, b"\xff\x06" + _varlen(len(name)) + name))

    tracks = [_track(conductor)]
    channel = 0
    for voice_name, voice in compiled.voices.items():
        is_drums = voice.get("instrument") == "drums"
        notes = [event for event in compiled.events if event.voice == voice_name]
        if not notes:
            continue
        if is_drums:
            use_channel = 9
        else:
            use_channel = channel
            channel += 1
            if channel == 9:
                channel = 10
            channel %= 16
        name = voice_name.encode("utf-8", "replace")[:60]
        events = [(0, 0, b"\xff\x03" + _varlen(len(name)) + name)]
        if not is_drums:
            program = INSTRUMENTS[voice["instrument"]]["gm"]
            events.append((0, 1, bytes([0xC0 | use_channel, program])))
        for note in notes:
            pitch = DRUM_MIDI[note.pitch] if is_drums else int(note.pitch)
            if not 0 <= pitch <= 127:
                continue
            start = tick(note.start_beat)
            end = max(start + 1, tick(note.end_beat))
            velocity = max(1, min(127, int(note.velocity * (1.15 if "!" in note.mods else 1.0) * 127)))
            events.append((start, 3, bytes([0x90 | use_channel, pitch, velocity])))
            events.append((end, 2, bytes([0x80 | use_channel, pitch, 0])))
        tracks.append(_track(events))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq)
    with open(path, "wb") as handle:
        handle.write(header + b"".join(tracks))


def write_spectrogram_png(path, stereo, sr, width=1400, height=500):
    """Draw a log-frequency spectrogram so structure can be checked by eye."""
    mono = stereo.mean(axis=1).astype(np.float64)
    window_size = 4096
    window = np.hanning(window_size)
    hops = np.linspace(0, max(len(mono) - window_size, 0), width).astype(np.int64)
    freqs = np.fft.rfftfreq(window_size, 1.0 / sr)
    edges = np.geomspace(40.0, min(16000.0, sr / 2), height + 1)
    bins = np.clip(np.searchsorted(freqs, edges), 1, len(freqs) - 1)
    image = np.zeros((height, width), dtype=np.float32)
    for column, hop in enumerate(hops):
        frame = mono[hop:hop + window_size]
        if len(frame) < window_size:
            frame = np.pad(frame, (0, window_size - len(frame)))
        magnitude = np.abs(np.fft.rfft(frame * window))
        cumulative = np.concatenate(([0.0], np.cumsum(magnitude)))
        for row in range(height):
            low, high = bins[row], max(bins[row + 1], bins[row] + 1)
            image[height - 1 - row, column] = (cumulative[high] - cumulative[low]) / (high - low)
    decibels = 20.0 * np.log10(image + 1e-4)
    level = np.clip((decibels + 40.0) / 75.0, 0.0, 1.0)
    # Dark navy through orange to pale yellow.
    stops = np.array([[10, 12, 40], [70, 30, 110], [200, 70, 70], [250, 170, 60], [255, 245, 200]], dtype=np.float32)
    position = level * (len(stops) - 1)
    lower = np.minimum(position.astype(np.int32), len(stops) - 2)
    blend = (position - lower)[..., None]
    rgb = (stops[lower] * (1.0 - blend) + stops[lower + 1] * blend).astype(np.uint8)

    raw = b"".join(b"\x00" + row.tobytes() for row in rgb)

    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))

    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        handle.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        handle.write(chunk(b"IEND", b""))
