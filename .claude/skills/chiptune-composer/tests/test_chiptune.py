"""Run with: .venv/bin/python -m unittest discover -s .claude/skills/chiptune-composer/tests"""

import json
import struct
import sys
import tempfile
import unittest
import wave
from unittest import mock
from pathlib import Path

import numpy as np

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))

import render  # noqa: E402
import score  # noqa: E402
import synth  # noqa: E402

EXAMPLES = sorted((SKILL / "assets" / "examples").glob("*.json"))


def tiny_song(**changes):
    song = {
        "title": "Test",
        "bpm": 120,
        "meter": "4/4",
        "key": "C major",
        "voices": {
            "lead": {"instrument": "pulse_lead"},
            "pad": {"instrument": "strings", "layer": "calm"},
            "kit": {"instrument": "drums"},
        },
        "sections": {
            "intro": {"bars": 1, "parts": {"lead": "C5:4"}},
            "main": {"bars": 2, "parts": {
                "lead": "E5:1 G5:1 C6:2 | G5:4",
                "pad": "C4+E4+G4:8",
                "kit": "{kick:1 hat:1 snare:1 hat:1 |}*2",
            }},
        },
        "arrangement": ["intro", "main"],
        "loop_from": 1,
    }
    song.update(changes)
    return song


def compile_(song, section=None):
    return score.compile_song(song, synth.INSTRUMENTS, synth.DRUM_NAMES, section)


class ParsingTests(unittest.TestCase):
    def parse(self, text, bars=1, bar_len=4, drums=False):
        return score.parse_part(text, score.Fraction(bar_len), bars, drums, synth.DRUM_NAMES)

    def test_pitches(self):
        self.assertEqual(score.parse_pitch("A4"), 69)
        self.assertEqual(score.parse_pitch("C4"), 60)
        self.assertEqual(score.parse_pitch("F#5"), 78)
        self.assertEqual(score.parse_pitch("Bb3"), 58)

    def test_triplets_add_up_exactly(self):
        tokens = self.parse("C5:1/3 D5:1/3 E5:1/3 F5:3")
        self.assertEqual(len(tokens), 4)

    def test_rounded_triplet_is_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("C5:0.33 D5:0.33 E5:0.33 F5:3")

    def test_bad_bar_names_the_bar(self):
        with self.assertRaisesRegex(ValueError, "bar 2 has 3"):
            self.parse("C5:4 | D5:3 | E5:4", bars=3)

    def test_wrong_total_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "total is 3"):
            self.parse("C5:3")

    def test_nested_repeats(self):
        tokens = self.parse("{ {C5:1/2}*2 D5:1 }*2")
        self.assertEqual(len(tokens), 6)

    def test_tie_merges_across_barline(self):
        tokens = self.parse("C5:4& | C5:2 D5:2", bars=2)
        self.assertEqual(tokens[0].dur, 6)
        self.assertEqual(len(tokens), 2)

    def test_tie_to_other_pitch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "same pitch"):
            self.parse("C5:2& D5:2")

    def test_decimal_with_staccato_mod(self):
        token = self.parse("C5:0.5. r:3.5")[0]
        self.assertEqual(token.dur, score.Fraction(1, 2))
        self.assertIn(".", token.mods)

    def test_unknown_drum_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown drum"):
            self.parse("cowbell:4", drums=True)


class CompileTests(unittest.TestCase):
    def test_all_problems_reported_together(self):
        song = tiny_song(voices={"lead": {"instrument": "kazoo"}})
        song["sections"]["main"]["parts"] = {"ghost": "C5:8"}
        with self.assertRaises(score.SongError) as caught:
            compile_(song)
        text = str(caught.exception)
        self.assertIn("kazoo", text)
        self.assertIn("ghost", text)

    def test_transpose_shifts_notes_not_drums(self):
        song = tiny_song(arrangement=[{"section": "main", "transpose": 2}], loop_from=0)
        compiled = compile_(song)
        lead = [e for e in compiled.events if e.voice == "lead"]
        self.assertEqual(lead[0].pitch, score.parse_pitch("F#5"))
        self.assertTrue(all(isinstance(e.pitch, str) for e in compiled.events if e.voice == "kit"))

    def test_swing_delays_only_offbeats(self):
        self.assertEqual(score._swung(1.0, 0.66), 1.0)
        self.assertAlmostEqual(score._swung(1.5, 0.66), 1.66)
        self.assertEqual(score._swung(1.5, 0), 1.5)

    def test_arp_spreads_chord_into_steps(self):
        song = tiny_song()
        song["voices"]["lead"]["arp"] = 0.25
        song["sections"]["intro"]["parts"]["lead"] = "C4+E4+G4:4"
        events = [e for e in compile_(song).events if e.voice == "lead" and e.segment == 0]
        self.assertEqual(len(events), 16)
        self.assertEqual([e.pitch for e in events[:4]], [60, 64, 67, 60])

    def test_section_override_tempo(self):
        song = tiny_song()
        song["sections"]["intro"]["bpm"] = 60
        compiled = compile_(song)
        self.assertAlmostEqual(compiled.segments[0].end_s, 4.0)
        self.assertAlmostEqual(compiled.segments[1].end_s, 8.0)


class LintTests(unittest.TestCase):
    def warnings(self, song):
        return score.lint(song, synth.INSTRUMENTS, synth.DRUM_NAMES)

    def test_clean_song_has_none(self):
        self.assertEqual(self.warnings(tiny_song()), [])

    def test_flags_out_of_range(self):
        song = tiny_song()
        song["sections"]["intro"]["parts"]["lead"] = "C2:4"
        self.assertTrue(any("outside" in w for w in self.warnings(song)))

    def test_flags_semitone_clash(self):
        song = tiny_song()
        song["sections"]["main"]["parts"]["pad"] = "F4:8"
        song["sections"]["main"]["parts"]["lead"] = "E4:8"
        song["voices"]["lead"]["instrument"] = "square"
        self.assertTrue(any("clashes" in w for w in self.warnings(song)))

    def test_flags_wrong_bass_at_chord_change(self):
        song = tiny_song()
        song["voices"]["low"] = {"instrument": "bass"}
        song["sections"]["intro"]["chords"] = "C"
        song["sections"]["intro"]["parts"]["low"] = "D2:4"
        self.assertTrue(any("bass plays" in w for w in self.warnings(song)))

    def test_flags_foreign_long_note(self):
        song = tiny_song()
        song["sections"]["intro"]["chords"] = "C"
        song["sections"]["intro"]["parts"]["lead"] = "F#5:4"
        self.assertTrue(any("neither the chord nor the key" in w for w in self.warnings(song)))

    def test_slash_chord_parsing(self):
        tones, bass = score.parse_chord("A/C#")
        self.assertEqual(bass, 1)
        self.assertIn(9, tones)


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sr = 22050
        cls.result = render.render_song(tiny_song(), sr=cls.sr)

    def test_same_input_gives_identical_audio(self):
        again = render.render_song(tiny_song(), sr=self.sr)
        self.assertTrue(np.array_equal(self.result["mix"], again["mix"]))

    def test_loop_points_match_the_score(self):
        start, end = self.result["loop"]
        self.assertEqual(start, 2 * self.sr)
        self.assertEqual(end, 6 * self.sr)
        self.assertEqual(self.result["mix"].shape[0], end)

    def test_stems_sum_to_mix(self):
        total = sum(self.result["layers"].values())
        self.assertLess(float(np.max(np.abs(total - self.result["mix"]))), 1e-5)
        self.assertEqual(set(self.result["layers"]), {"base", "calm"})

    def test_never_clips(self):
        self.assertLessEqual(float(np.max(np.abs(self.result["mix"]))), 0.9)

    def test_seam_has_no_click_and_tail_wraps(self):
        # A long note crossing the loop end must continue at the loop start.
        song = tiny_song(arrangement=["main"], loop_from=0)
        song["voices"]["lead"] = {"instrument": "strings"}
        song["sections"]["main"]["parts"] = {"lead": "C4+E4+G4:8"}
        result = render.render_song(song, sr=self.sr)
        report = render.analyze(result)
        self.assertTrue(report["loop_seam_ok"], report)
        start_level = float(np.max(np.abs(result["mix"][:200])))
        self.assertGreater(start_level, 0.0005, "release and reverb tail should wrap to the start")

    def test_looped_pass_matches_continuous_playback(self):
        # The defining property of a seamless loop: one looped pass must be identical
        # to the middle pass of the same music played three times in a row.
        with mock.patch.object(render, "HUMANIZE_SECONDS", 0.0):
            looped = render.render_song(tiny_song(arrangement=["main"], loop_from=0), sr=self.sr)
            song = tiny_song(arrangement=["main", "main", "main"], loop=False)
            song.pop("loop_from")
            continuous = render.render_song(song, sr=self.sr)
        length = looped["loop"][1]
        for name in looped["layers"]:
            one = looped["layers"][name]
            middle = continuous["layers"][name][length:2 * length]
            scale = float(np.abs(middle).max()) / float(np.abs(one).max())
            self.assertLess(float(np.abs(one * scale - middle).max()), 1e-3, name)

    def test_one_shot_keeps_tail_and_has_no_loop(self):
        song = tiny_song(loop=False, arrangement=["main"])
        song.pop("loop_from")
        result = render.render_song(song, sr=self.sr)
        self.assertIsNone(result["loop"])
        self.assertGreater(result["mix"].shape[0], 4 * self.sr)

    def test_pitch_is_correct(self):
        note = synth.render_note(synth.INSTRUMENTS["square"], 69, 1.0, 0.8, "", 44100, 1)[:, 0]
        spectrum = np.abs(np.fft.rfft(note * np.hanning(len(note))))
        peak = np.fft.rfftfreq(len(note), 1 / 44100)[int(np.argmax(spectrum))]
        self.assertAlmostEqual(peak, 440.0, delta=2.0)

    def test_every_instrument_and_drum_is_finite_and_audible(self):
        for name, params in synth.INSTRUMENTS.items():
            low, high = params["range"]
            for midi in (low, high):
                note = synth.render_note(params, midi, 0.4, 0.8, "!^~", 22050, 3)
                self.assertTrue(np.isfinite(note).all(), name)
                self.assertGreater(float(np.max(np.abs(note))), 0.02, name)
        for name in synth.DRUM_NAMES:
            hit = synth.render_drum(name, 0.4, 0.8, "", 22050, 3)
            self.assertTrue(np.isfinite(hit).all(), name)
            self.assertGreater(float(np.max(np.abs(hit))), 0.02, name)

    def test_voice_param_typo_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown instrument parameter"):
            synth.resolve_params({"instrument": "square", "params": {"dutty": 0.2}})


class OutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.result = render.render_song(tiny_song(), sr=22050)
        cls.written, cls.meta = render.write_outputs(cls.result, cls.dir.name, "t", preview=True)
        cls.folder = Path(cls.dir.name) / "t"

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_wav_reads_back_with_loop_chunk(self):
        path = self.folder / "t.wav"
        with wave.open(str(path)) as handle:
            self.assertEqual(handle.getnchannels(), 2)
            self.assertEqual(handle.getframerate(), 22050)
            self.assertEqual(handle.getnframes(), self.result["mix"].shape[0])
        raw = path.read_bytes()
        at = raw.index(b"smpl")
        size = struct.unpack("<I", raw[at + 4:at + 8])[0]
        fields = struct.unpack("<15I", raw[at + 8:at + 8 + size])
        self.assertEqual(fields[7], 1)
        self.assertEqual((fields[11], fields[12]), (self.result["loop"][0], self.result["loop"][1] - 1))

    def test_stems_and_preview_exist(self):
        self.assertTrue((self.folder / "t_stem_calm.wav").exists())
        self.assertTrue((self.folder / "t_stem_base.wav").exists())
        with wave.open(str(self.folder / "t_loop_preview.wav")) as handle:
            start, end = self.result["loop"]
            self.assertEqual(handle.getnframes(), end + (end - start))

    def test_midi_structure(self):
        raw = (self.folder / "t.mid").read_bytes()
        self.assertEqual(raw[:4], b"MThd")
        fmt, tracks, ppq = struct.unpack(">HHH", raw[8:14])
        self.assertEqual((fmt, tracks, ppq), (1, 4, 480))
        self.assertEqual(raw.count(b"MTrk"), 4)
        self.assertEqual(raw.count(b"\xff\x2f\x00"), 4)

    def test_png_signature(self):
        self.assertEqual((self.folder / "t_spectrogram.png").read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_metadata_records_loop(self):
        meta = json.loads((self.folder / "t.json").read_text())
        self.assertEqual(meta["loop_start_sample"], self.result["loop"][0])
        self.assertEqual(meta["clipped_samples"], 0)


class ExampleTests(unittest.TestCase):
    def test_examples_compile_and_lint_clean(self):
        self.assertGreaterEqual(len(EXAMPLES), 4)
        for path in EXAMPLES:
            song = json.loads(path.read_text())
            compile_(song)
            self.assertEqual(score.lint(song, synth.INSTRUMENTS, synth.DRUM_NAMES), [], path.name)


class SoundEffects(unittest.TestCase):
    def test_every_effect_renders_cleanly(self):
        import sfx
        for name in sfx.EFFECTS:
            self.assertEqual(sfx.check(name, sfx.render(name))["problems"], [], name)

    def test_effects_repeat_exactly(self):
        import sfx
        self.assertTrue(np.array_equal(sfx.render("FlakBurst"), sfx.render("FlakBurst")))


class OrchestralVoices(unittest.TestCase):
    def test_section_voices_change_nothing_for_older_instruments(self):
        for name, params in synth.INSTRUMENTS.items():
            if not name.startswith("orch_"):
                self.assertEqual(params["body"], (), name)
                self.assertEqual(params["drift_cents"], 0.0, name)
                self.assertEqual(params["onset_spread"], 0.0, name)


if __name__ == "__main__":
    unittest.main()
