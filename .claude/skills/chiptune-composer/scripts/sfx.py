#!/usr/bin/env python3
"""Sound effects built from the same math as the music: no samples, no third-party audio.

    sfx.py --out output/sfx                 render every effect
    sfx.py --out output/sfx --only Name     render some of them
    sfx.py --list                           print the names

Each effect is a function below, named exactly as the game names it. Renders are deterministic.
The report's numbers stand in for listening: it fails an effect that clips, is nearly silent,
starts or ends on a click, or (for loops) doesn't join up with itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import output  # noqa: E402
import synth  # noqa: E402

SR = 44100
TARGET_PEAK = 0.84
TWO_PI = 2.0 * np.pi
EFFECTS = {}
LOOPS = set()


def effect(function):
    EFFECTS[function.__name__] = function
    return function


def looping(function):
    LOOPS.add(function.__name__)
    return effect(function)


def clock(seconds):
    return np.arange(int(seconds * SR)) / SR


def rng_for(name):
    return np.random.default_rng(synth.stable_seed("sfx", name))


def white(n, rng):
    return rng.standard_normal(n) * 0.5


def low(signal, cutoff):
    return synth.lowpass(signal, cutoff, SR)


def high(signal, cutoff):
    return signal - low(signal, cutoff)


def band(signal, lower, upper):
    return high(low(signal, upper), lower)


def sweep(freq):
    """A sine following a frequency curve."""
    return np.sin(TWO_PI * np.cumsum(freq) / SR)


def decay(t, tau, start=0.0):
    return np.exp(-np.maximum(t - start, 0.0) / tau) * (t >= start)


def rise(t, seconds):
    return np.clip(t / max(seconds, 1e-4), 0.0, 1.0)


def swell(t, peak_at):
    """Rises to its peak, then falls away to the end of the clip."""
    end = t[-1]
    return np.where(t < peak_at, (t / peak_at) ** 2, ((end - t) / (end - peak_at)) ** 1.6)


def at(buffer, start_seconds, sound, gain=1.0):
    start = int(start_seconds * SR)
    end = min(start + len(sound), len(buffer))
    buffer[start:end] += sound[: end - start] * gain
    return buffer


def stereo(left, right=None):
    return np.stack((left, left if right is None else right), axis=1)


def wide(mono, rng, ms=9.0):
    """Widens a sound with a slightly delayed copy on one side."""
    lag = int(ms * SR / 1000)
    return stereo(mono, np.concatenate((np.zeros(lag), mono[:-lag])))


def metal(t, freqs, tau, gain=1.0):
    return gain * sum(np.sin(TWO_PI * f * t) * decay(t, tau * (1.0 - i * 0.09)) for i, f in enumerate(freqs)) / len(freqs)


def boom(t, rng, pitch=60.0, tau=0.3):
    """A short low thud, the weight under most impacts."""
    return sweep(pitch + pitch * 1.4 * np.exp(-t / 0.03)) * decay(t, tau)


def creak_wave(t, rng, pitch=95.0, speed=31.0):
    """Wood under strain: a stick-slip buzz whose rate wanders."""
    wander = pitch * (1.0 + 0.3 * np.sin(TWO_PI * 1.3 * t + rng.uniform(0, 6)) + 0.15 * np.sin(TWO_PI * 3.7 * t))
    phase = np.cumsum(wander) / SR
    saw = 2.0 * (phase % 1.0) - 1.0
    stick = 0.55 + 0.45 * np.sign(np.sin(TWO_PI * speed * t + 4.0 * np.sin(TWO_PI * 2.1 * t)))
    return band(saw * stick, 180.0, 2400.0)


# ---- Flight ----

@effect
def ShipRoll():
    """A hard sideways barrel roll: rushing air and timbers leaning over."""
    rng = rng_for("roll")
    t = clock(0.75)
    air = band(white(len(t), rng), 280.0, 3200.0) * swell(t, 0.3)
    timbers = creak_wave(t, rng, 80.0) * swell(t, 0.4) * 0.28
    pan = np.sin(np.pi * np.clip(t / 0.55, 0, 1)) * 0.75
    mono = air + timbers
    return stereo(mono * (1.0 - pan * 0.5), mono * (1.0 + pan * 0.5))


@effect
def BoostIgnite():
    """The engines opening up."""
    rng = rng_for("boost")
    t = clock(1.0)
    roar = low(white(len(t), rng), 900.0) * rise(t, 0.08) * decay(t, 0.42)
    whine = sweep(120.0 + 520.0 * np.clip(t / 0.5, 0, 1) ** 0.6) * rise(t, 0.05) * decay(t, 0.34) * 0.3
    thump = boom(t, rng, 48.0, 0.14)
    return wide(roar * 1.3 + whine + thump, rng)


@looping
def EngineLoop():
    """The steady thrum of lift engines, seamless and low, for the whole of a dogfight."""
    rng = rng_for("engine")
    seconds = 4.0
    t = clock(seconds)
    # Whole-number cycle counts over the loop mean every partial joins up exactly.
    wave = sum(gain * np.sin(TWO_PI * round(f * seconds) / seconds * t + rng.uniform(0, 6))
               for f, gain in ((46.0, 1.0), (47.0, 0.7), (92.0, 0.45), (138.0, 0.25), (184.0, 0.12), (231.0, 0.07)))
    flutter = 0.82 + 0.18 * np.sin(TWO_PI * 11.0 * t)
    spectrum = np.fft.rfft(rng.standard_normal(len(t)))
    freqs = np.fft.rfftfreq(len(t), 1.0 / SR)
    spectrum[(freqs < 90.0) | (freqs > 700.0)] = 0.0  # Filtering the whole circular buffer keeps the seam.
    rumble = np.fft.irfft(spectrum, len(t))
    rumble = rumble / np.max(np.abs(rumble)) * 0.32
    other = np.roll(rumble, len(t) // 3)
    return stereo(wave * flutter * 0.3 + rumble, wave * flutter * 0.3 + other)


@effect
def NearMiss():
    """A shot tearing past after a good dodge."""
    rng = rng_for("nearmiss")
    t = clock(0.42)
    whine = sweep(1900.0 * np.exp(-t / 0.32) + 220.0) * swell(t, 0.1) * 0.3
    air = band(white(len(t), rng), 900.0, 6500.0) * swell(t, 0.1) * 0.8
    pan = np.clip(t / 0.3, 0, 1) * 2.0 - 1.0
    mono = whine + air
    return stereo(mono * (1.0 - pan * 0.7), mono * (1.0 + pan * 0.7))


@effect
def ShotWhiz():
    """A round going wide somewhere close."""
    rng = rng_for("whiz")
    t = clock(0.28)
    return wide((band(white(len(t), rng), 1100.0, 5200.0) + sweep(1300.0 - 900.0 * t / t[-1]) * 0.12) * swell(t, 0.07), rng, 4.0)


@effect
def FlakBurst():
    """A sharp mid-air crack and the patter of shrapnel."""
    rng = rng_for("flak")
    t = clock(0.8)
    crack = band(white(len(t), rng), 500.0, 7000.0) * decay(t, 0.035)
    body = boom(t, rng, 95.0, 0.12) * 0.8
    patter = high(white(len(t), rng), 2500.0) * (rng.random(len(t)) > 0.994) * decay(t, 0.3, 0.06) * 6.0
    return wide(crack * 1.6 + body + low(patter, 9000.0) * 0.5, rng)


@effect
def MortarBurst():
    """A heavy shell going off in open air."""
    rng = rng_for("mortar")
    t = clock(1.1)
    blast = low(white(len(t), rng), 1400.0) * decay(t, 0.2)
    return wide(blast * 1.5 + boom(t, rng, 52.0, 0.34) * 1.1, rng)


@effect
def TimberBreak():
    """A floating wreck or rock outcrop shattering."""
    rng = rng_for("timber")
    t = clock(0.9)
    out = boom(t, rng, 80.0, 0.12) * 0.9
    for lag, gain in ((0.0, 1.0), (0.05, 0.7), (0.12, 0.6), (0.21, 0.4), (0.33, 0.25), (0.47, 0.15)):
        snap = band(white(len(t), rng), 500.0, 4200.0) * decay(t, 0.024, lag)
        out = out + snap * gain * 1.5
    return wide(out, rng)


@effect
def JellyPop():
    """A storm jellyfish bursting: a wet pop and a fizz of charge."""
    rng = rng_for("jelly")
    t = clock(0.6)
    pop = sweep(180.0 + 720.0 * (1.0 - np.exp(-t / 0.04))) * decay(t, 0.07)
    fizz = high(white(len(t), rng), 3400.0) * (0.5 + 0.5 * np.sign(np.sin(TWO_PI * 62.0 * t))) * decay(t, 0.2, 0.03)
    return wide(pop + fizz * 0.6, rng)


@effect
def Raked():
    """A broadside walking along a hull: a run of hits, each a little different."""
    rng = rng_for("raked")
    t = clock(0.85)
    out = np.zeros(len(t))
    for i, lag in enumerate((0.0, 0.07, 0.15, 0.22, 0.31, 0.38)):
        tail = t[: len(t) - int(lag * SR)]
        hit = low(white(len(tail), rng), 2400.0) * decay(tail, 0.06) * 1.4 + boom(tail, rng, 84.0 + i * 9.0, 0.09) * 0.7
        hit = hit + metal(tail, (640.0 + i * 70.0, 1130.0 + i * 50.0, 1830.0), 0.09, 0.45)
        at(out, lag, hit, 1.0 - i * 0.09)
    return wide(out, rng)


@effect
def WarHorn():
    """A long low war horn, for reinforcements and the start of a fight."""
    t = clock(2.3)
    env = rise(t, 0.2) * np.clip((t[-1] - t) / 0.7, 0, 1)
    pitch = 98.0 * 2.0 ** ((-70.0 * np.exp(-t / 0.2) + 8.0 * np.sin(TWO_PI * 4.6 * t) * rise(t - 0.8, 0.5)) / 1200.0)
    phase = np.cumsum(pitch) / SR
    tone = sum(np.sin(TWO_PI * n * phase) / n ** 0.8 for n in range(1, 13))
    second = sum(np.sin(TWO_PI * n * phase * 1.5) / n ** 0.9 for n in range(1, 9))
    return wide(low(tone + second * 0.5, 1700.0) * env, rng_for("horn"), 14.0)


@effect
def DangerSting():
    """A falling brass hit for bad news, in place of the bright sting."""
    t = clock(1.4)
    out = np.zeros(len(t))
    for midi, gain in ((48, 1.0), (51, 0.8), (54, 0.8), (60, 0.7)):
        f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        pitch = f * 2.0 ** (-160.0 * np.clip(t - 0.35, 0, None) / 1200.0)
        phase = np.cumsum(pitch) / SR
        out += gain * sum(np.sin(TWO_PI * n * phase) / n for n in range(1, 11))
    return wide(low(out, 2600.0) * rise(t, 0.012) * decay(t, 0.5) * 0.45, rng_for("danger"), 12.0)


@effect
def HullCreak():
    """The hull groaning as the anchor crushes it against the bottom of the sky."""
    rng = rng_for("creak")
    t = clock(1.0)
    groan = creak_wave(t, rng, 58.0, 19.0) * swell(t, 0.35)
    rumble = low(white(len(t), rng), 170.0) * swell(t, 0.3) * 1.2
    return wide(groan + rumble, rng, 12.0)


@effect
def ShipFlyby():
    """Something large pulling away and leaving the fight."""
    rng = rng_for("flyby")
    t = clock(1.5)
    pitch = 150.0 * 2.0 ** (-(t / t[-1]) * 0.9)
    tone = sum(np.sin(TWO_PI * n * np.cumsum(pitch) / SR) / n for n in (1, 2, 3))
    air = band(white(len(t), rng), 200.0, 1600.0)
    env = swell(t, 0.4)
    pan = np.clip(t / t[-1], 0, 1) * 1.6 - 0.8
    mono = (tone * 0.34 + air) * env
    return stereo(mono * (1.0 - pan * 0.6), mono * (1.0 + pan * 0.6))


@effect
def GliderLaunch():
    """A catapult thunk and a light glider screaming away."""
    rng = rng_for("glider")
    t = clock(0.85)
    thunk = boom(t, rng, 120.0, 0.05) + metal(t, (900.0, 1500.0), 0.03, 0.5)
    scream = sweep(320.0 + 1500.0 * np.clip(t / 0.7, 0, 1) ** 1.3) * rise(t - 0.04, 0.1) * np.clip((t[-1] - t) / 0.45, 0, 1) * 0.2
    air = band(white(len(t), rng), 1000.0, 5200.0) * swell(t, 0.25) * 0.45
    return wide(thunk + scream + air, rng)


# ---- Hooks and grapples ----

@effect
def HookThrow():
    """A grappling line whirling out."""
    rng = rng_for("hookthrow")
    t = clock(0.5)
    whirl = 0.4 + 0.6 * np.abs(np.sin(np.pi * (9.0 * t + 8.0 * t * t)))
    return wide(band(white(len(t), rng), 500.0, 3400.0) * whirl * swell(t, 0.22), rng)


@effect
def HookLand():
    """Iron biting into timber."""
    rng = rng_for("hookland")
    t = clock(0.45)
    clank = metal(t, (1180.0, 1730.0, 2610.0, 3350.0), 0.09, 1.2)
    wood = band(white(len(t), rng), 300.0, 2600.0) * decay(t, 0.03)
    return wide(clank + wood * 1.6 + boom(t, rng, 130.0, 0.06) * 0.7, rng, 5.0)


@effect
def RopeSnap():
    """Grappling lines parting under load."""
    rng = rng_for("rope")
    t = clock(0.5)
    crack = high(white(len(t), rng), 1500.0) * decay(t, 0.012) * 2.2
    twang = sweep(420.0 * np.exp(-t / 0.2) + 110.0) * decay(t, 0.14) * 0.5
    lash = band(white(len(t), rng), 900.0, 4600.0) * decay(t, 0.04, 0.08)
    return wide(crack + twang + lash, rng, 4.0)


@effect
def ChainTaut():
    """A harpoon chain snapping tight between two ships."""
    rng = rng_for("chain")
    t = clock(0.9)
    out = boom(t, rng, 66.0, 0.18) * 1.1
    for i, lag in enumerate((0.0, 0.08, 0.15, 0.21, 0.26, 0.3, 0.34)):
        tail = t[: len(t) - int(lag * SR)]
        at(out, lag, metal(tail, (1420.0 + i * 90.0, 2230.0, 3170.0 - i * 60.0), 0.05, 0.8), 1.0 - i * 0.1)
    return wide(out, rng, 6.0)


@effect
def MissileLaunch():
    """A rocket lighting off and streaking away."""
    rng = rng_for("missile")
    t = clock(1.3)
    ignite = low(white(len(t), rng), 2000.0) * decay(t, 0.05) * 1.4 + boom(t, rng, 70.0, 0.1)
    roar = band(white(len(t), rng), 300.0, 5000.0) * rise(t, 0.05) * np.clip((t[-1] - t) / 0.9, 0, 1) ** 1.5 * 0.9
    howl = sweep(260.0 + 540.0 * t) * rise(t, 0.1) * np.clip((t[-1] - t) / 0.8, 0, 1) * 0.16
    return wide(ignite + roar + howl, rng)


@effect
def Overdrive():
    """A Lift-Core running past its limit: a rising electric surge."""
    rng = rng_for("overdrive")
    t = clock(1.2)
    pitch = 90.0 + 620.0 * np.clip(t / 0.75, 0, 1) ** 1.6
    phase = np.cumsum(pitch) / SR
    buzz = low(2.0 * (phase % 1.0) - 1.0, 3200.0) * rise(t, 0.04) * np.clip((t[-1] - t) / 0.5, 0, 1) * 0.42
    crackle = high(white(len(t), rng), 3000.0) * (rng.random(len(t)) > 0.97) * swell(t, 0.7) * 2.0
    return wide(buzz + low(crackle, 9000.0) * 0.5, rng)


@effect
def SignatureFire():
    """A ship's signature move going off: a charged thump and a bright rush."""
    rng = rng_for("signature")
    t = clock(1.0)
    charge = sweep(200.0 + 900.0 * np.clip(t / 0.22, 0, 1)) * rise(t, 0.03) * decay(t, 0.2, 0.2) * 0.35
    thump = boom(t - 0.0, rng, 60.0, 0.22)
    air = band(white(len(t), rng), 600.0, 7000.0) * swell(t, 0.2) * 0.7
    return wide(charge + thump + air, rng)


@effect
def Pickup():
    """Lift-Stone taken aboard: a bright crystalline shimmer."""
    t = clock(1.0)
    out = np.zeros(len(t))
    for i, midi in enumerate((76, 83, 88, 95)):
        tail = t[: len(t) - int(i * 0.06 * SR)]
        f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        at(out, i * 0.06, (np.sin(TWO_PI * f * tail) + 0.4 * np.sin(TWO_PI * f * 2.76 * tail)) * decay(tail, 0.28), 0.8)
    return wide(out, rng_for("pickup"), 11.0)


@effect
def WhaleGulp():
    """The sky whale's jaws closing over the ship."""
    rng = rng_for("gulp")
    t = clock(2.2)
    bite = boom(t, rng, 42.0, 0.5) * 1.5
    crunch = band(white(len(t), rng), 240.0, 2400.0) * (0.3 + 0.7 * (rng.random(len(t)) > 0.97)) * decay(t, 0.2, 0.02)
    moan = sweep(80.0 - 34.0 * (t / t[-1])) * swell(t, 0.5) * 0.7
    swallow = sweep(55.0 + 26.0 * np.sin(TWO_PI * 1.7 * t)) * decay(t, 0.45, 0.9) * 0.5
    return wide(bite + crunch * 0.9 + moan + swallow, rng, 13.0)


# ---- Weather and warnings ----

@effect
def ThunderRumble():
    """Thunder building, the warning before lightning falls."""
    rng = rng_for("rumble")
    t = clock(1.6)
    rumble = low(white(len(t), rng), 190.0) * (0.6 + 0.4 * np.sin(TWO_PI * 5.0 * t + 1.0)) * swell(t, 0.9) * 2.6
    fizz = high(white(len(t), rng), 4200.0) * swell(t, 1.3) * 0.08
    return wide(rumble + fizz, rng, 14.0)


@effect
def LightningCrack():
    """A close strike: a split-second tear and the thunder behind it."""
    rng = rng_for("lightning")
    t = clock(1.7)
    tear = high(white(len(t), rng), 1800.0) * decay(t, 0.022) * 2.4
    second = high(white(len(t), rng), 1200.0) * decay(t, 0.018, 0.045) * 1.4
    thunder = low(white(len(t), rng), 240.0) * rise(t - 0.02, 0.05) * decay(t, 0.46) * 3.0
    return wide(tear + second + thunder + boom(t, rng, 44.0, 0.3), rng, 7.0)


@effect
def ThunderDistant():
    """Thunder a long way off, under deck fights in a storm."""
    rng = rng_for("distant")
    t = clock(2.4)
    return wide(low(white(len(t), rng), 150.0) * (0.55 + 0.45 * np.sin(TWO_PI * 3.1 * t)) * swell(t, 0.6) * 3.0, rng, 16.0)


@effect
def VolleyWarning():
    """A bosun's whistle from the enemy deck: they're about to fire."""
    rng = rng_for("volley")
    t = clock(0.55)
    pitch = np.where(t < 0.2, 1500.0 + 900.0 * t / 0.2, 2400.0)
    tone = sweep(pitch * 2.0 ** (10.0 * np.sin(TWO_PI * 24.0 * t) / 1200.0)) * rise(t, 0.015) * np.clip((t[-1] - t) / 0.1, 0, 1)
    return wide(tone * 0.55 + band(white(len(t), rng), 1500.0, 4200.0) * 0.05, rng, 6.0)


@effect
def HullAlarm():
    """The ship's bell, hammered: the hull is failing."""
    t = clock(1.5)
    out = np.zeros(len(t))
    for lag in (0.0, 0.26, 0.52, 0.78):
        tail = t[: len(t) - int(lag * SR)]
        at(out, lag, metal(tail, (880.0, 1391.0, 1978.0, 2640.0, 3487.0), 0.32, 1.5), 0.85)
    return wide(out, rng_for("alarm"), 8.0)


# ---- Deck fights ----

@effect
def Pistol():
    """A flintlock: lock click, flash and a sharp report."""
    rng = rng_for("pistol")
    t = clock(0.6)
    click = high(white(len(t), rng), 3500.0) * decay(t, 0.004) * 1.2
    report = band(white(len(t), rng), 420.0, 6800.0) * decay(t, 0.05, 0.012) * 2.0
    return wide(click + report + boom(t, rng, 120.0, 0.07), rng, 5.0)


@effect
def MagicCast():
    """Lift-Core energy thrown from the hand, a rising shimmer and a release."""
    rng = rng_for("magic")
    t = clock(0.8)
    out = np.zeros(len(t))
    for detune in (1.0, 1.007, 1.5, 2.01):
        out += sweep(detune * (300.0 + 1100.0 * np.clip(t / 0.3, 0, 1))) * rise(t, 0.05) * decay(t, 0.2, 0.25) * 0.26
    return wide(out + band(white(len(t), rng), 2600.0, 9000.0) * swell(t, 0.28) * 0.35, rng, 12.0)


@effect
def GuardUp():
    """Stance set and blade raised."""
    rng = rng_for("guard")
    t = clock(0.4)
    return wide(metal(t, (1540.0, 2310.0, 3120.0), 0.08, 0.9) + band(white(len(t), rng), 300.0, 1800.0) * decay(t, 0.05) * 1.2 + boom(t, rng, 110.0, 0.05) * 0.5, rng, 5.0)


@effect
def BladeClash():
    """Steel on steel, for parries and counters."""
    rng = rng_for("clash")
    t = clock(0.65)
    ring = metal(t, (2150.0, 3370.0, 4620.0, 5810.0), 0.17, 1.8)
    scrape = high(white(len(t), rng), 3000.0) * decay(t, 0.03) * 1.4
    return wide(ring + scrape, rng, 4.0)


@effect
def BodyFall():
    """A fighter hitting the deck."""
    rng = rng_for("fall")
    t = clock(0.55)
    out = boom(t, rng, 88.0, 0.08) + band(white(len(t), rng), 150.0, 900.0) * decay(t, 0.04) * 1.2
    second = t[: len(t) - int(0.14 * SR)]
    at(out, 0.14, boom(second, rng, 110.0, 0.05) + band(white(len(second), rng), 200.0, 1100.0) * decay(second, 0.025), 0.5)
    return wide(out, rng, 8.0)


@effect
def Burn():
    """Flames licking at someone."""
    rng = rng_for("burn")
    t = clock(0.7)
    sizzle = high(white(len(t), rng), 2600.0) * rise(t, 0.02) * decay(t, 0.22) * 0.8
    crackle = band(white(len(t), rng), 800.0, 5200.0) * (rng.random(len(t)) > 0.985) * decay(t, 0.3) * 5.0
    whoomp = low(white(len(t), rng), 420.0) * swell(t, 0.08) * 1.3
    return wide(sizzle + crackle + whoomp, rng, 7.0)


@effect
def StatusHit():
    """A status taking hold: a dark, wobbling pulse."""
    t = clock(0.55)
    pitch = 330.0 * 2.0 ** (-t / t[-1]) * 2.0 ** (40.0 * np.sin(TWO_PI * 13.0 * t) / 1200.0)
    return wide((sweep(pitch) + 0.4 * sweep(pitch * 1.49)) * rise(t, 0.02) * decay(t, 0.2) * 0.8, rng_for("status"), 9.0)


@effect
def Stunned():
    """Knocked senseless: ringing ears and a falling warble."""
    t = clock(0.85)
    wobble = 2.0 ** (90.0 * np.sin(TWO_PI * 8.0 * t) / 1200.0)
    tone = sweep(1250.0 * wobble) + 0.6 * sweep(1880.0 * wobble)
    return wide(tone * rise(t, 0.01) * decay(t, 0.3) * 0.5, rng_for("stun"), 10.0)


@effect
def BossRoar():
    """A boss enraged, a deep inhuman bellow with no words in it."""
    rng = rng_for("roar")
    t = clock(1.5)
    pitch = 76.0 + 34.0 * np.sin(np.pi * np.clip(t / t[-1], 0, 1)) + 4.0 * np.sin(TWO_PI * 17.0 * t)
    phase = np.cumsum(pitch) / SR
    throat = sum(np.sin(TWO_PI * n * phase) / n ** 0.7 for n in range(1, 21))
    throat = synth._body_filter(throat, ((520.0, 12.0, 0.6), (1120.0, 8.0, 0.5)), SR)
    growl = band(white(len(t), rng), 120.0, 1500.0) * (0.5 + 0.5 * np.sin(TWO_PI * 31.0 * t))
    env = rise(t, 0.09) * np.clip((t[-1] - t) / 0.6, 0, 1)
    return wide(low(throat * 0.5, 3000.0) * env + growl * env * 1.1, rng, 13.0)


@effect
def Revive():
    """A fallen crewmate back on deck: a warm rising swell."""
    t = clock(1.1)
    out = np.zeros(len(t))
    for i, midi in enumerate((60, 67, 72, 76, 79)):
        tail = t[: len(t) - int(i * 0.09 * SR)]
        f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        at(out, i * 0.09, (np.sin(TWO_PI * f * tail) + 0.3 * np.sin(TWO_PI * f * 2.0 * tail)) * rise(tail, 0.03) * decay(tail, 0.34), 0.62)
    return wide(out, rng_for("revive"), 11.0)


@effect
def GrappleSwing():
    """The boarding party swinging across on lines and landing."""
    rng = rng_for("swing")
    t = clock(1.05)
    air = band(white(len(t), rng), 300.0, 2300.0) * swell(t, 0.5)
    rope = creak_wave(t, rng, 120.0, 27.0) * swell(t, 0.3) * 0.2
    out = air + rope
    landing = t[: len(t) - int(0.82 * SR)]
    at(out, 0.82, boom(landing, rng, 96.0, 0.07) + band(white(len(landing), rng), 180.0, 1000.0) * decay(landing, 0.035) * 1.3, 1.2)
    return wide(out, rng, 10.0)


@effect
def Plunder():
    """A chest thrown open on a pile of gold."""
    rng = rng_for("plunder")
    t = clock(1.2)
    out = band(white(len(t), rng), 240.0, 1800.0) * decay(t, 0.03) * 1.0 + boom(t, rng, 120.0, 0.05) * 0.6
    for lag in rng.uniform(0.04, 0.8, 26):
        tail = t[: len(t) - int(lag * SR)]
        f = rng.uniform(2800.0, 6400.0)
        at(out, lag, metal(tail, (f, f * 1.37, f * 1.81), 0.05, 0.9), rng.uniform(0.25, 0.7) * (1.0 - lag))
    return wide(out, rng, 7.0)


# ---- Menus and rewards ----

@effect
def CoinPurchase():
    """Coins counted out on a table."""
    rng = rng_for("coin")
    t = clock(0.42)
    out = np.zeros(len(t))
    for lag, f in ((0.0, 3350.0), (0.07, 4120.0), (0.13, 3680.0), (0.2, 4470.0)):
        tail = t[: len(t) - int(lag * SR)]
        at(out, lag, metal(tail, (f, f * 1.41, f * 2.03), 0.05, 1.3))
    return wide(out, rng, 5.0)


@effect
def AmmoLoad():
    """A breech slid shut on a new round."""
    rng = rng_for("ammo")
    t = clock(0.32)
    slide = band(white(len(t), rng), 700.0, 3800.0) * swell(t, 0.1) * 0.8
    tail = t[: len(t) - int(0.14 * SR)]
    out = slide.copy()
    at(out, 0.14, metal(tail, (980.0, 1620.0, 2440.0), 0.05, 1.3) + boom(tail, rng, 150.0, 0.03) * 0.5)
    return wide(out, rng, 4.0)


@effect
def LevelUp():
    """A rising brass-and-bell flourish for a crewmate reaching a new level."""
    t = clock(1.5)
    out = np.zeros(len(t))
    for i, midi in enumerate((67, 72, 76, 79, 84)):
        tail = t[: len(t) - int(i * 0.1 * SR)]
        f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        brass = sum(np.sin(TWO_PI * n * f * tail) / n ** 1.2 for n in range(1, 8)) * rise(tail, 0.015) * decay(tail, 0.22)
        bell = (np.sin(TWO_PI * f * 2.0 * tail) + 0.35 * np.sin(TWO_PI * f * 5.4 * tail)) * decay(tail, 0.4) * 0.5
        at(out, i * 0.1, brass + bell, 0.46 if i < 4 else 0.7)
    return wide(out, rng_for("levelup"), 11.0)


def check(name, signal):
    """What a person would notice first: clipping, silence and clicks at either end."""
    problems = []
    peak = float(np.max(np.abs(signal)))
    if peak >= 0.9999:
        problems.append("clips")
    rms = float(np.sqrt(np.mean(signal ** 2)))
    if rms < 0.01:
        problems.append("nearly silent")
    if name in LOOPS:
        jump = float(np.max(np.abs(signal[-1] - signal[0])))
        typical = float(np.percentile(np.abs(np.diff(signal, axis=0)), 99.9))
        if jump > max(typical * 1.5, 0.02):
            problems.append(f"loop seam jumps {jump:.3f}")
    else:
        if float(np.max(np.abs(signal[0]))) > 0.01:
            problems.append("starts with a click")
        if float(np.max(np.abs(signal[-1]))) > 0.01:
            problems.append("ends with a click")
    return {"seconds": round(signal.shape[0] / SR, 3), "peak_dbfs": round(20.0 * np.log10(max(peak, 1e-9)), 2),
            "rms_dbfs": round(20.0 * np.log10(max(rms, 1e-9)), 2), "problems": problems}


def render(name):
    """Renders one effect: DC removed, faded at the ends and normalized."""
    signal = np.asarray(EFFECTS[name](), dtype=np.float64)
    if signal.ndim == 1:
        signal = stereo(signal)
    signal = signal - signal.mean(axis=0, keepdims=True)
    peak = float(np.max(np.abs(signal))) or 1.0
    signal = signal / peak * TARGET_PEAK
    if name not in LOOPS:
        n_in, n_out = int(0.002 * SR), min(int(0.03 * SR), signal.shape[0] // 3)
        signal[:n_in] *= np.linspace(0.0, 1.0, n_in)[:, None]
        signal[-n_out:] *= np.linspace(1.0, 0.0, n_out)[:, None]
    return signal.astype(np.float32)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render sound effects.")
    parser.add_argument("--out", default="output/sfx")
    parser.add_argument("--only", nargs="*", help="render just these effects")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(EFFECTS))
        return 0
    unknown = set(args.only or []) - set(EFFECTS)
    if unknown:
        print(f"ERROR: unknown effects: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    failed = 0
    for name in args.only or EFFECTS:
        signal = render(name)
        output.write_wav(out / f"{name}.wav", signal, SR)
        report[name] = check(name, signal)
        failed += bool(report[name]["problems"])
        print(f"{name:16s} {report[name]['seconds']:5.2f}s  peak {report[name]['peak_dbfs']:6.2f}  rms {report[name]['rms_dbfs']:7.2f}  {'; '.join(report[name]['problems'])}")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{len(report)} effects, {failed} with problems, in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
