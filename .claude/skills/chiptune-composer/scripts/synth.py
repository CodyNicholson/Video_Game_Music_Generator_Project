"""A self-written chip synthesizer: oscillators, FM, LFSR noise, drums and reverb.

Every sound is computed from math here. There are no samples, SoundFonts or
third-party audio assets, so nothing in the output carries someone else's license.
NumPy supplies array arithmetic only.

Instruments are data, so a song can override any parameter per voice. The palette
translates an orchestra and big band into chip voices in the spirit of the
FM-and-PSG sound of late-90s console music.
"""

from __future__ import annotations

import zlib

import numpy as np

TWO_PI = 2.0 * np.pi

_BASE = {
    "osc": "pulse", "duty": 0.5, "pwm_rate": 0.0, "pwm_depth": 0.0,
    "ratio": 1.0, "index": 1.5, "index_floor": 0.5, "index_attack": 0.06,
    "ratio2": 0.0, "index2": 0.0,
    "attack": 0.004, "decay": 0.1, "sustain": 0.8, "release": 0.06, "gate": 0.94,
    "vibrato_rate": 5.5, "vibrato_cents": 0.0, "vibrato_delay": 0.25,
    "unison": 1, "detune": 0.0, "spread": 0.0,
    "cutoff": 0.0, "cutoff_mult": 0.0, "dark_cutoff": 0.0, "dark_time": 0.08,
    "breath": 0.0, "breath_clock": 16000.0, "sub": 0.0,
    "tremolo_rate": 0.0, "tremolo_depth": 0.0, "bits": 0,
    "scoop_cents": 180.0, "scoop_time": 0.07, "fall_cents": 900.0,
    "glide_cents": 0.0, "glide_time": 0.03,
    "reverb": 0.15, "level": 1.0, "one_shot": 0.0,
    "range": (24, 108), "role": "melody", "gm": 80,
}


def _inst(**overrides):
    return {**_BASE, **overrides}


INSTRUMENTS = {
    # Brass: 2-op FM whose brightness opens with the attack and with loudness, the
    # same behaviour that makes real brass and SEGA FM patches feel alive.
    "trumpet": _inst(osc="fm", index=2.6, index_floor=0.35, index_attack=0.05, ratio2=2.0, index2=0.25,
                     attack=0.012, decay=0.12, sustain=0.82, release=0.07, vibrato_cents=14, vibrato_delay=0.28,
                     level=0.72, reverb=0.2, range=(52, 88), gm=56),
    "trumpet_section": _inst(osc="fm", index=2.4, index_floor=0.4, index_attack=0.04, ratio2=2.0, index2=0.2,
                             attack=0.01, decay=0.1, sustain=0.78, release=0.06, unison=3, detune=7, spread=0.45,
                             level=0.56, reverb=0.2, range=(52, 88), gm=61),
    "horn": _inst(osc="fm", index=1.25, index_floor=0.45, index_attack=0.09, attack=0.035, decay=0.2, sustain=0.85,
                  release=0.14, cutoff=2800, unison=2, detune=4, spread=0.3, vibrato_cents=7, vibrato_delay=0.4,
                  level=0.72, reverb=0.3, range=(41, 77), gm=60),
    "trombone": _inst(osc="fm", index=2.2, index_floor=0.35, index_attack=0.06, ratio2=2.0, index2=0.15,
                      attack=0.018, decay=0.12, sustain=0.8, release=0.08, cutoff=3400, unison=2, detune=4, spread=0.2,
                      scoop_cents=120, level=0.68, reverb=0.16, range=(36, 72), gm=57),
    "sax": _inst(osc="fm", index=2.0, index_floor=0.65, index_attack=0.03, ratio2=3.0, index2=0.25, attack=0.012,
                 decay=0.08, sustain=0.85, release=0.06, breath=0.018, vibrato_cents=20, vibrato_delay=0.18,
                 cutoff=5200, level=0.66, reverb=0.18, range=(49, 84), gm=65),
    # Strings: detuned, softly filtered saws, a chip stand-in for a section.
    "strings": _inst(osc="saw", attack=0.11, decay=0.3, sustain=0.92, release=0.3, unison=5, detune=9, spread=0.85,
                     cutoff=3600, vibrato_cents=8, vibrato_rate=5.0, vibrato_delay=0.2, gate=1.0,
                     level=0.3, reverb=0.42, range=(36, 100), gm=48),
    "strings_stab": _inst(osc="saw", attack=0.006, decay=0.13, sustain=0.28, release=0.1, unison=4, detune=10, spread=0.8,
                          cutoff=5200, level=0.36, reverb=0.3, range=(36, 100), gm=48),
    "strings_chip": _inst(osc="pulse", duty=0.32, pwm_rate=0.8, pwm_depth=0.16, attack=0.02, decay=0.2, sustain=0.75,
                          release=0.12, unison=2, detune=8, spread=0.7, vibrato_cents=8, cutoff=6200,
                          level=0.26, reverb=0.32, range=(40, 100), gm=50),
    "pizz": _inst(osc="tri", attack=0.001, decay=0.14, sustain=0.0, release=0.07, gate=1.0, unison=2, detune=5, spread=0.3,
                  level=0.72, reverb=0.26, range=(36, 96), gm=45),
    # Dramatic orchestra: fast string figures, a soaring section lead, low weight and a choir-like pad.
    "strings_ostinato": _inst(osc="saw", attack=0.003, decay=0.09, sustain=0.25, release=0.05, unison=3, detune=9, spread=0.7,
                              cutoff=4200, gate=1.0, level=0.42, reverb=0.2, range=(36, 96), gm=48),
    "strings_lead": _inst(osc="saw", attack=0.05, decay=0.3, sustain=0.9, release=0.2, unison=4, detune=6, spread=0.5,
                          cutoff=5000, vibrato_cents=14, vibrato_rate=5.4, vibrato_delay=0.16, gate=1.0,
                          level=0.42, reverb=0.42, range=(48, 103), gm=49),
    "low_strings": _inst(osc="saw", attack=0.01, decay=0.15, sustain=0.7, release=0.1, unison=3, detune=7, spread=0.4,
                         cutoff=1800, level=0.5, reverb=0.16, range=(28, 67), gm=42),
    "tuba": _inst(osc="fm", index=1.4, index_floor=0.5, index_attack=0.05, attack=0.02, decay=0.15, sustain=0.85, release=0.09,
                  cutoff=1400, sub=0.15, level=0.85, reverb=0.14, range=(24, 60), role="bass", gm=58),
    "choir_pad": _inst(osc="saw", attack=0.25, decay=0.4, sustain=0.9, release=0.4, unison=6, detune=6, spread=0.9, cutoff=1500,
                       vibrato_cents=6, vibrato_rate=4.6, vibrato_delay=0.3, breath=0.01, gate=1.0,
                       level=0.34, reverb=0.6, range=(45, 88), gm=52),
    # Woodwinds and folk voices.
    "flute": _inst(osc="tri", attack=0.035, decay=0.1, sustain=0.85, release=0.09, breath=0.035, breath_clock=20000,
                   vibrato_cents=15, vibrato_rate=5.2, vibrato_delay=0.2, level=0.72, reverb=0.32, range=(60, 98), gm=73),
    "clarinet": _inst(osc="pulse", duty=0.5, attack=0.018, decay=0.08, sustain=0.85, release=0.05, cutoff=2600,
                      vibrato_cents=6, vibrato_delay=0.35, level=0.52, reverb=0.2, range=(50, 92), gm=71),
    "oboe": _inst(osc="pulse", duty=0.18, attack=0.014, decay=0.08, sustain=0.85, release=0.05, cutoff=4400,
                  vibrato_cents=11, vibrato_delay=0.22, level=0.52, reverb=0.2, range=(58, 91), gm=68),
    "whistle": _inst(osc="sine", attack=0.012, decay=0.06, sustain=0.85, release=0.05, breath=0.03, breath_clock=22000,
                     vibrato_cents=20, vibrato_rate=6.0, vibrato_delay=0.16, level=0.62, reverb=0.32, range=(62, 100), gm=78),
    "accordion": _inst(osc="pulse", duty=0.36, attack=0.018, decay=0.06, sustain=0.9, release=0.05, unison=3, detune=7,
                       spread=0.4, cutoff=4600, tremolo_rate=6.2, tremolo_depth=0.09, level=0.4, reverb=0.2,
                       range=(48, 91), gm=21),
    "guitar": _inst(osc="pulse", duty=0.3, attack=0.001, decay=0.45, sustain=0.0, release=0.1, gate=1.0, cutoff=5200,
                    dark_cutoff=1100, dark_time=0.09, level=0.62, reverb=0.18, range=(40, 84), gm=24),
    "harp": _inst(osc="tri", attack=0.001, decay=0.65, sustain=0.0, release=0.25, gate=1.0, level=0.68,
                  reverb=0.42, range=(36, 96), gm=46),
    "bell": _inst(osc="fm", ratio=3.51, index=1.5, index_floor=0.1, index_attack=0.0, attack=0.001, decay=0.7, sustain=0.0,
                  release=0.3, gate=1.0, level=0.4, reverb=0.45, range=(60, 103), gm=14),
    # Pure chip voices.
    "pulse_lead": _inst(osc="pulse", duty=0.25, attack=0.003, decay=0.08, sustain=0.72, release=0.05, vibrato_cents=16,
                        vibrato_delay=0.22, level=0.44, reverb=0.2, range=(48, 96), gm=80),
    "square": _inst(osc="pulse", duty=0.5, attack=0.002, decay=0.06, sustain=0.68, release=0.03, level=0.4, reverb=0.12,
                    range=(36, 96), gm=80),
    "arp": _inst(osc="pulse", duty=0.125, attack=0.001, decay=0.07, sustain=0.55, release=0.02, gate=1.0, level=0.3,
                 reverb=0.2, range=(48, 100), gm=81),
    # Bass and low percussion.
    "bass": _inst(osc="tri", attack=0.002, decay=0.14, sustain=0.72, release=0.05, sub=0.22, bits=16, level=0.82,
                  reverb=0.03, range=(24, 60), role="bass", gm=38),
    "upright": _inst(osc="tri", attack=0.002, decay=0.32, sustain=0.12, release=0.08, gate=1.0, sub=0.25, cutoff=1500,
                     level=0.9, reverb=0.05, range=(24, 60), role="bass", gm=32),
    "timpani": _inst(osc="sine", attack=0.002, decay=0.5, sustain=0.0, release=0.5, gate=1.0, one_shot=0.8, breath=0.14,
                     breath_clock=2600, glide_cents=70, glide_time=0.09, cutoff=900, level=0.82, reverb=0.3,
                     range=(36, 60), role="bass", gm=47),
}

DRUM_MIDI = {"kick": 36, "snare": 38, "rim": 37, "clap": 39, "hat": 42, "ohat": 46, "ride": 51, "crash": 49,
             "tom_hi": 48, "tom_lo": 43, "shaker": 70, "tamb": 54, "brush": 40, "swell": 57,
             "bdrum": 35, "gong": 52}
DRUM_NAMES = frozenset(DRUM_MIDI)

_lfsr_cache = {}


def _lfsr(short):
    """A 15-bit linear-feedback shift register, the noise source of classic chip audio."""
    if short not in _lfsr_cache:
        state = 1
        tap = 6 if short else 1
        length = 93 if short else 32767
        bits = np.empty(length, dtype=np.float32)
        for i in range(length):
            bits[i] = 1.0 if state & 1 else -1.0
            feedback = (state & 1) ^ ((state >> tap) & 1)
            state = (state >> 1) | (feedback << 14)
        _lfsr_cache[short] = bits
    return _lfsr_cache[short]


def _noise(n, clock, sr, offset=0, short=False):
    table = _lfsr(short)
    indices = (offset + (np.arange(n) * clock / sr).astype(np.int64)) % len(table)
    return table[indices].astype(np.float64)


def _poly_blep(phase, dt):
    """Soften each waveform step so high notes do not alias into harsh inharmonics."""
    out = np.zeros_like(phase)
    rising = phase < dt
    x = phase[rising] / dt[rising]
    out[rising] = x + x - x * x - 1.0
    falling = phase > 1.0 - dt
    x = (phase[falling] - 1.0) / dt[falling]
    out[falling] = x * x + x + x + 1.0
    return out


def lowpass(signal, cutoff, sr):
    """Second-order magnitude response applied in the frequency domain."""
    if cutoff <= 0 or cutoff >= sr / 2 or len(signal) < 8:
        return signal
    pad = min(2048, len(signal))
    spectrum = np.fft.rfft(signal, len(signal) + pad)
    freqs = np.fft.rfftfreq(len(signal) + pad, 1.0 / sr)
    spectrum /= np.sqrt(1.0 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spectrum)[: len(signal)]


def _oscillator(params, phase_total, freq_hz, t, vel, accent, sr):
    kind = params["osc"]
    phase = phase_total % 1.0
    dt = np.clip(freq_hz / sr, 1e-6, 0.45)
    if kind == "sine":
        return np.sin(TWO_PI * phase)
    if kind == "tri":
        wave = 4.0 * np.abs(phase - 0.5) - 1.0
        return wave
    if kind == "saw":
        return 2.0 * phase - 1.0 - _poly_blep(phase, dt)
    if kind == "pulse":
        duty = params["duty"]
        if params["pwm_depth"]:
            duty = np.clip(duty + params["pwm_depth"] * np.sin(TWO_PI * params["pwm_rate"] * t), 0.05, 0.95)
        wave = np.where(phase < duty, 1.0, -1.0)
        wave = wave + _poly_blep(phase, dt) - _poly_blep((phase + 1.0 - duty) % 1.0, dt)
        return wave
    if kind == "fm":
        attack = params["index_attack"]
        shape = np.minimum(t / attack, 1.0) if attack > 0 else np.exp(-t / 0.15)
        floor = params["index_floor"]
        # Tame the index on high notes, where large FM sidebands would alias.
        tame = np.minimum(1.0, 1400.0 / np.maximum(freq_hz, 1.0))
        loud = (0.55 + 0.65 * vel) * (1.25 if accent else 1.0)
        index = params["index"] * (floor + (1.0 - floor) * shape) * loud * tame
        modulator = np.sin(TWO_PI * params["ratio"] * phase_total)
        if params["ratio2"]:
            modulator = modulator + params["index2"] * np.sin(TWO_PI * params["ratio2"] * phase_total)
        return np.sin(TWO_PI * phase_total + index * modulator)
    raise ValueError(f"unknown oscillator {kind!r}")


def _envelope(params, n_gate, n_total, sr):
    t = np.arange(n_total) / sr
    attack = max(params["attack"], 0.0005)
    decay = max(params["decay"], 0.001)
    sustain = params["sustain"]
    held = sustain + (1.0 - sustain) * np.exp(-np.maximum(t - attack, 0.0) / decay)
    env = np.minimum(t / attack, 1.0) * held
    n_gate = min(max(n_gate, 1), n_total)
    n_release = n_total - n_gate
    if n_release > 0:
        tail_t = np.arange(n_release) / max(n_release, 1)
        env[n_gate:] = env[n_gate - 1] * np.exp(-4.5 * tail_t) * (1.0 - tail_t)
    return env


def render_note(params, midi, duration, velocity, mods, sr, seed):
    """Render one pitched note as a stereo array of shape (samples, 2)."""
    rng = np.random.default_rng(seed)
    if "." in mods:
        gate = 0.5
    elif "-" in mods:
        gate = 1.0
    else:
        gate = params["gate"]
    sound_time = duration * gate
    if params["one_shot"]:
        sound_time = max(sound_time, params["one_shot"])
    release = params["release"]
    n_gate = max(int(sound_time * sr), 8)
    n_total = n_gate + int(release * sr) + 1
    t = np.arange(n_total) / sr
    base = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    accent = "!" in mods
    vel = float(np.clip(velocity * (1.18 if accent else 1.0), 0.0, 1.0))

    cents = np.zeros(n_total)
    depth = params["vibrato_cents"] * (2.0 if "~" in mods else 1.0)
    if depth:
        delay = params["vibrato_delay"]
        fade = np.clip((t - delay) / 0.2, 0.0, 1.0)
        cents += depth * fade * np.sin(TWO_PI * params["vibrato_rate"] * t + rng.uniform(0, TWO_PI))
    if "^" in mods:
        cents -= params["scoop_cents"] * np.exp(-t / max(params["scoop_time"] / 3.0, 1e-3))
    if params["glide_cents"]:
        cents += params["glide_cents"] * np.exp(-t / params["glide_time"])
    fade_out = None
    if "v" in mods:
        # Big-band fall: the pitch drops away and the note thins out as it ends.
        start = 0.55 * n_gate / sr
        progress = np.clip((t - start) / max(n_gate / sr - start, 1e-3), 0.0, 1.0)
        cents -= params["fall_cents"] * progress ** 2
        fade_out = 1.0 - 0.75 * progress ** 2

    left = np.zeros(n_total)
    right = np.zeros(n_total)
    voices = max(int(params["unison"]), 1)
    for voice in range(voices):
        spread_pos = (2.0 * voice / (voices - 1) - 1.0) if voices > 1 else 0.0
        detune = params["detune"] * spread_pos
        freq = base * 2.0 ** ((cents + detune) / 1200.0)
        phase = np.cumsum(freq) / sr + rng.uniform(0, 1)
        wave = _oscillator(params, phase, freq, t, vel, accent, sr)
        if params["bits"]:
            steps = float(params["bits"]) / 2.0
            wave = np.round(wave * steps) / steps
        if params["sub"]:
            wave = wave + params["sub"] * np.sin(np.pi * phase)  # one octave down
        pan = params["spread"] * spread_pos
        angle = (pan + 1.0) * np.pi / 4.0
        left += wave * np.cos(angle)
        right += wave * np.sin(angle)
    scale = np.sqrt(2.0 / voices)
    left *= scale
    right *= scale

    def tone_filter(channel):
        cutoff = params["cutoff"] or params["cutoff_mult"] * base
        out = lowpass(channel, cutoff, sr) if cutoff else channel
        if params["dark_cutoff"]:
            # Plucks start bright and darken, mimicking a string losing its overtones.
            dark = lowpass(channel, params["dark_cutoff"], sr)
            mix = np.exp(-t / params["dark_time"])
            out = mix * out + (1.0 - mix) * dark
        return out

    left = tone_filter(left)
    right = tone_filter(right)
    env = _envelope(params, n_gate, n_total, sr)
    if params["breath"]:
        hiss = _noise(n_total, params["breath_clock"], sr, offset=int(rng.integers(0, 30000)))
        hiss = lowpass(hiss, 7000 if params["breath_clock"] > 5000 else 1400, sr) * params["breath"]
        left = left + hiss
        right = right + hiss
    if params["tremolo_depth"]:
        env = env * (1.0 + params["tremolo_depth"] * np.sin(TWO_PI * params["tremolo_rate"] * t))
    if fade_out is not None:
        env = env * fade_out
    amplitude = params["level"] * vel ** 1.4
    return np.stack((left * env, right * env), axis=1) * amplitude


def render_drum(name, duration, velocity, mods, sr, seed):
    """Build a drum hit from swept sines and LFSR noise."""
    rng = np.random.default_rng(seed)
    offset = int(rng.integers(0, 30000))
    accent = "!" in mods
    vel = float(np.clip(velocity * (1.2 if accent else 1.0), 0.0, 1.0)) ** 1.3

    def clock(seconds):
        return np.arange(int(seconds * sr)) / sr

    def hiss(n, rate, short=False):
        return _noise(n, rate, sr, offset, short)

    if name == "kick":
        t = clock(0.28)
        freq = 48.0 + 110.0 * np.exp(-t / 0.035)
        body = np.sin(TWO_PI * np.cumsum(freq) / sr) * np.exp(-t / 0.11)
        click = hiss(len(t), 9000) * np.exp(-t / 0.003) * 0.28
        wave = (body + click) * 1.1
        pan = 0.0
    elif name == "snare":
        t = clock(0.24)
        body = np.sin(TWO_PI * np.cumsum(170.0 + 70.0 * np.exp(-t / 0.018)) / sr) * np.exp(-t / 0.05) * 0.55
        rattle = lowpass(hiss(len(t), 15000), 8500, sr) * np.exp(-t / 0.075) * 0.72
        wave = body + rattle
        pan = 0.04
    elif name == "rim":
        t = clock(0.05)
        wave = np.sin(TWO_PI * 1720.0 * t) * np.exp(-t / 0.008) * 0.55
        pan = -0.1
    elif name == "clap":
        t = clock(0.2)
        bursts = sum(np.exp(-np.maximum(t - lag, 0.0) / 0.012) * (t >= lag) for lag in (0.0, 0.012, 0.025))
        tail = np.exp(-t / 0.07) * 0.4
        wave = hiss(len(t), 12000) * (bursts * 0.45 + tail) * 0.72
        pan = 0.08
    elif name in ("hat", "ohat"):
        length, tau = (0.06, 0.016) if name == "hat" else (0.34, 0.1)
        t = clock(length)
        noise = hiss(len(t), 32000)
        wave = (noise - lowpass(noise, 6500, sr)) * np.exp(-t / tau) * 0.42
        pan = 0.18
    elif name == "ride":
        t = clock(0.65)
        tone = sum(np.sin(TWO_PI * f * t) for f in (3120.0, 4470.0, 6090.0)) / 3.0
        noise = hiss(len(t), 30000)
        wash = noise - lowpass(noise, 7000, sr)
        wave = (tone * 0.42 * np.exp(-t / 0.16) + wash * 0.2 * np.exp(-t / 0.2)) * 0.82
        pan = -0.2
    elif name == "crash":
        t = clock(1.5)
        noise = hiss(len(t), 30000)
        wave = (noise - lowpass(noise, 3200, sr) * 0.82) * np.exp(-t / 0.42) * 0.42
        pan = 0.24
    elif name in ("tom_hi", "tom_lo"):
        base = 175.0 if name == "tom_hi" else 105.0
        t = clock(0.3)
        wave = np.sin(TWO_PI * np.cumsum(base + base * 0.55 * np.exp(-t / 0.03)) / sr) * np.exp(-t / 0.11)
        wave = wave + hiss(len(t), 6000) * np.exp(-t / 0.012) * 0.15
        pan = 0.16 if name == "tom_hi" else -0.16
    elif name == "shaker":
        t = clock(0.07)
        noise = hiss(len(t), 26000)
        wave = (noise - lowpass(noise, 5400, sr)) * np.minimum(t / 0.008, 1.0) * np.exp(-t / 0.02) * 0.34
        pan = -0.26
    elif name == "tamb":
        t = clock(0.13)
        noise = hiss(len(t), 30000)
        jingle = np.sin(TWO_PI * 6800.0 * t) * 0.32
        wave = ((noise - lowpass(noise, 7200, sr)) * 0.6 + jingle) * np.exp(-t / 0.04) * 0.42
        pan = 0.3
    elif name == "brush":
        t = clock(0.12)
        noise = lowpass(hiss(len(t), 18000), 8200, sr)
        wave = noise * np.minimum(t / 0.012, 1.0) * np.exp(-t / 0.038) * 0.3
        pan = 0.05
    elif name == "bdrum":
        # Concert bass drum: lower, longer and softer-edged than a kit kick.
        t = clock(0.7)
        body = np.sin(TWO_PI * np.cumsum(52.0 + 34.0 * np.exp(-t / 0.05)) / sr) * np.exp(-t / 0.26)
        wave = (body + lowpass(hiss(len(t), 5000), 900, sr) * np.exp(-t / 0.03) * 0.3) * 1.15
        pan = 0.0
    elif name == "gong":
        t = clock(3.0)
        partials = sum(gain * np.sin(TWO_PI * f * t) for f, gain in
                       ((97.0, 0.6), (143.0, 0.45), (211.0, 0.38), (317.0, 0.26), (463.0, 0.18), (691.0, 0.12)))
        noise = hiss(len(t), 22000)
        wash = (noise - lowpass(noise, 2500, sr)) * np.minimum(t / 0.12, 1.0) * np.exp(-t / 0.55) * 0.16
        wave = (partials * np.exp(-t / 0.95) * 0.62 + wash)
        pan = -0.06
    elif name == "swell":
        # Cymbal roll that grows to its end; the token's duration sets its length.
        t = clock(max(duration, 0.2))
        noise = hiss(len(t), 30000)
        rise = (t / t[-1]) ** 2.4
        wave = (noise - lowpass(noise, 3200, sr) * 0.82) * rise * 0.36
        pan = -0.12
    else:
        raise ValueError(f"unknown drum {name!r}")

    # A 1 ms ramp removes the digital click of a hit starting at full level.
    ramp = min(int(0.001 * sr), len(wave))
    wave = wave * vel
    wave[:ramp] *= np.linspace(0.0, 1.0, ramp, endpoint=False)
    angle = (pan + 1.0) * np.pi / 4.0
    return np.stack((wave * np.cos(angle), wave * np.sin(angle)), axis=1)


def impulse_response(sr, seconds=1.7, predelay=0.018):
    """A small hall made of shaped noise, standing in for console-era DSP reverb."""
    rng = np.random.default_rng(1998)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    decay = np.exp(-t * 6.9 / seconds)
    channels = []
    for channel in range(2):
        tail = rng.standard_normal(n) * decay
        tail = lowpass(tail, 5200, sr)
        tail[: int(predelay * sr)] = 0.0
        early = np.zeros(n)
        for delay, gain in zip(rng.uniform(0.008, 0.07, 6), rng.uniform(0.25, 0.55, 6)):
            early[int(delay * sr)] += gain * (1 if channel == 0 else -1)
        ir = tail / np.sqrt(np.sum(tail ** 2)) + early * 0.32
        channels.append(ir)
    return np.stack(channels, axis=1)


def convolve_stereo(signal, ir):
    """Fast convolution; the result is longer than the input by the reverb tail."""
    length = signal.shape[0] + ir.shape[0] - 1
    size = int(2 ** np.ceil(np.log2(max(length, 2))))
    out = np.zeros((length, 2), dtype=np.float32)
    for channel in range(2):
        spectrum = np.fft.rfft(signal[:, channel], size) * np.fft.rfft(ir[:, channel], size)
        out[:, channel] = np.fft.irfft(spectrum, size)[:length]
    return out


def stable_seed(*parts):
    """Deterministic across runs, unlike Python's salted hash(), so renders repeat."""
    return zlib.crc32("|".join(str(part) for part in parts).encode("utf-8"))


def resolve_params(voice):
    """Merge a voice's `params` overrides over its instrument, rejecting typos."""
    instrument = voice["instrument"]
    params = dict(INSTRUMENTS[instrument])
    overrides = voice.get("params") or {}
    unknown = set(overrides) - set(_BASE)
    if unknown:
        raise ValueError(f"unknown instrument parameter(s): {', '.join(sorted(unknown))}")
    params.update(overrides)
    return params
