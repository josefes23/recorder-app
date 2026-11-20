"""El acabado: qué se valida, qué se recorta y que el audio y el color hagan lo que dicen."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.domain.errors import ValidationError
from app.domain.finish import (
    KEEP_GAP, KEEP_TAIL, LOOK_IDS, Finish, read_finish, tighten_plan, validate_finish,
)
from app.domain.production import validate_production
from app.domain.video import RenderSpec
from app.infrastructure.finish import (
    channel_curves, ffmpeg_exe, make_grade, measure_loudness, normalize_loudness, parse_loudnorm,
    split_highlights, card_frame, tighten_audio,
)
from app.domain.finish import ColorFinish


def w(text, start, end):
    return {"text": text, "start": start, "end": end}


class ValidationTests(unittest.TestCase):
    def test_nothing_asked_means_nothing_done(self):
        for empty in (None, {}, {"audio": {}, "color": {}}):
            finish = validate_finish(empty)
            self.assertEqual(finish, Finish())
            self.assertFalse(finish.active)

    def test_what_arrives_is_cleaned_and_clamped(self):
        finish = validate_finish({
            "audio": {"normalize": 1},
            "color": {"look": "cine", "exposure": 7, "contrast": "-0.254", "saturation": None},
            "cards": {"intro": "  Lo  que *nadie*  dice ", "outro": "x" * 500},
        })
        self.assertTrue(finish.audio.normalize)
        self.assertFalse(finish.audio.clean)
        self.assertEqual((finish.color.exposure, finish.color.contrast, finish.color.saturation), (1.0, -0.25, 0.0))
        self.assertEqual(finish.cards.intro, "Lo que *nadie* dice")
        self.assertEqual(len(finish.cards.outro), 120)
        self.assertTrue(finish.active)

    def test_rubbish_is_refused_with_a_reason(self):
        for bad in ({"color": {"look": "sepia"}}, {"color": {"exposure": "mucho"}}, {"audio": "sí"}, "hola"):
            with self.assertRaises(ValidationError):
                validate_finish(bad)
        self.assertEqual(read_finish({"color": {"look": "sepia"}}), Finish())  # lo ya guardado no tumba nada

    def test_every_look_has_parameters(self):
        from app.infrastructure.finish import LOOK_PARAMS

        self.assertEqual(set(LOOK_PARAMS), set(LOOK_IDS))

    def test_it_travels_with_the_production_and_into_the_render(self):
        prod = validate_production({"finish": {"pace": {"tighten": True}}})
        self.assertTrue(prod.finish.pace.tighten)
        spec = RenderSpec.from_dict({"finish": prod.as_dict()["finish"]})
        self.assertTrue(read_finish(spec.finish).pace.tighten)
        self.assertEqual(RenderSpec.from_dict({}).finish, {})  # los videos de antes no traen nada


class TightenTests(unittest.TestCase):
    WORDS = [w("Hola", 0.1, 0.5), w("mundo", 0.6, 1.0), w("después", 2.5, 3.0), w("fin", 3.1, 3.4)]

    def test_a_long_pause_is_shortened_and_the_words_move_up(self):
        plan = tighten_plan(self.WORDS, 3.5)
        self.assertTrue(plan.changed)
        # La pausa de 1,5 s (1,0 → 2,5) queda en KEEP_GAP: se quitan 1,5 - KEEP_GAP.
        self.assertAlmostEqual(plan.removed, 1.5 - KEEP_GAP, places=3)
        self.assertAlmostEqual(plan.duration, 3.5 - plan.removed, places=3)
        before, after = plan.words[1], plan.words[2]
        self.assertAlmostEqual(after["start"] - before["end"], KEEP_GAP, places=3)
        self.assertEqual([x["text"] for x in plan.words], ["Hola", "mundo", "después", "fin"])
        # Lo anterior a la pausa no se mueve.
        self.assertEqual((plan.words[0]["start"], plan.words[1]["end"]), (0.1, 1.0))

    def test_the_kept_pieces_add_up_to_the_new_duration(self):
        plan = tighten_plan(self.WORDS, 3.5)
        self.assertAlmostEqual(sum(b - a for a, b in plan.keep), plan.duration, places=3)
        self.assertEqual(plan.keep[0][0], 0.0)

    def test_normal_pauses_are_left_alone(self):
        plan = tighten_plan([w("a", 0.1, 0.5), w("b", 0.8, 1.2)], 1.4)
        self.assertFalse(plan.changed)
        self.assertEqual(plan.keep, [(0.0, 1.4)])
        self.assertEqual(plan.duration, 1.4)

    def test_a_long_silence_at_the_end_is_trimmed(self):
        plan = tighten_plan([w("a", 0.1, 0.5)], 3.0)
        self.assertAlmostEqual(plan.duration, 0.5 + KEEP_TAIL, places=3)

    def test_no_words_means_no_cuts(self):
        self.assertFalse(tighten_plan([], 4.0).changed)

    def test_the_input_is_not_modified(self):
        words = [w("a", 0.1, 0.5), w("b", 2.0, 2.4)]
        tighten_plan(words, 3.0)
        self.assertEqual(words[1]["start"], 2.0)


class ColorTests(unittest.TestCase):
    FRAME = np.full((4, 6, 3), 128, dtype=np.uint8)

    def test_natural_does_nothing(self):
        self.assertIsNone(make_grade(ColorFinish()))

    def test_exposure_lightens_and_darkens(self):
        up = make_grade(ColorFinish(exposure=0.8))(self.FRAME)
        down = make_grade(ColorFinish(exposure=-0.8))(self.FRAME)
        self.assertGreater(int(up.mean()), 128)
        self.assertLess(int(down.mean()), 128)
        self.assertEqual(up.dtype, np.uint8)
        self.assertEqual(up.shape, self.FRAME.shape)

    def test_warm_pushes_red_over_blue_and_cool_the_opposite(self):
        warm = make_grade(ColorFinish(look="warm"))(self.FRAME)[0, 0]
        cool = make_grade(ColorFinish(look="cool"))(self.FRAME)[0, 0]
        self.assertGreater(int(warm[0]), int(warm[2]))
        self.assertGreater(int(cool[2]), int(cool[0]))

    def test_mono_has_no_color_left(self):
        frame = np.zeros((4, 6, 3), dtype=np.uint8)
        frame[..., 0], frame[..., 1], frame[..., 2] = 200, 80, 30
        out = make_grade(ColorFinish(look="mono"))(frame)
        self.assertTrue((out[..., 0] == out[..., 1]).all() and (out[..., 1] == out[..., 2]).all())

    def test_saturation_slider_changes_how_far_from_grey(self):
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        frame[..., 0], frame[..., 1], frame[..., 2] = 200, 100, 100
        more = make_grade(ColorFinish(saturation=0.8))(frame)[0, 0]
        less = make_grade(ColorFinish(saturation=-0.8))(frame)[0, 0]
        self.assertGreater(int(more[0]) - int(more[1]), 100)
        self.assertLess(int(less[0]) - int(less[1]), 100)

    def test_curves_are_monotonic_for_plain_adjustments(self):
        for curve in channel_curves(ColorFinish(exposure=0.4, contrast=0.4)):
            self.assertTrue((np.diff(curve.astype(int)) >= 0).all())


class CardTests(unittest.TestCase):
    def test_highlights_are_split_by_word(self):
        self.assertEqual(split_highlights("Lo que *nadie sabe* hoy"),
                         [("Lo", False), ("que", False), ("nadie", True), ("sabe", True), ("hoy", False)])

    def test_the_card_has_the_size_of_the_video_and_some_text_on_it(self):
        frame = card_frame("Suscríbete para *más*", (270, 480), None)
        self.assertEqual(frame.shape, (480, 270, 3))
        self.assertGreater(int(frame.max()), 200)  # hay letras claras sobre el fondo oscuro

    def test_a_very_long_text_still_fits(self):
        frame = card_frame("palabra " * 60, (270, 480), None)
        self.assertEqual(frame.shape, (480, 270, 3))


class LoudnessParseTests(unittest.TestCase):
    STDERR = """[Parsed_loudnorm_0 @ 0x1] \n{\n\t"input_i" : "-23.50",\n\t"input_tp" : "-4.10",\n\t"input_lra" : "3.20",
\t"input_thresh" : "-33.70",\n\t"output_i" : "-14.10",\n\t"target_offset" : "0.10"\n}\n"""

    def test_the_measurement_is_read_from_ffmpeg_output(self):
        heard = parse_loudnorm(self.STDERR)
        self.assertEqual((heard.integrated, heard.true_peak, heard.range, heard.threshold, heard.offset),
                         (-23.5, -4.1, 3.2, -33.7, 0.1))

    def test_garbage_is_an_engine_error(self):
        from app.domain.errors import EngineError

        with self.assertRaises(EngineError):
            parse_loudnorm("nada")


@unittest.skipUnless(shutil.which(ffmpeg_exe()) or Path(ffmpeg_exe()).is_file(), "sin ffmpeg")
class FfmpegTests(unittest.TestCase):
    """Con ffmpeg de verdad: un audio de prueba, recortado y normalizado."""

    def _tone(self, folder: Path, name: str, expression: str, seconds: float) -> Path:
        out = folder / name
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", expression, "-t", str(seconds),
             "-ar", "44100", "-ac", "2", str(out)],
            check=True,
        )
        return out

    def test_tightening_makes_the_audio_as_short_as_the_plan_says(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src = self._tone(folder, "in.wav", "sine=frequency=440", 4.0)
            plan = tighten_plan([w("a", 0.1, 1.0), w("b", 3.0, 3.8)], 4.0)
            out = folder / "out.mp3"
            tighten_audio(src, plan.keep, out)
            probe = subprocess.run([ffmpeg_exe(), "-i", str(out)], capture_output=True, text=True).stderr
            hours, minutes, seconds = probe.split("Duration: ")[1].split(",")[0].split(":")
            lasted = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            self.assertAlmostEqual(lasted, plan.duration, delta=0.15)

    def test_normalizing_brings_a_quiet_and_a_loud_audio_to_the_same_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            quiet = self._tone(folder, "q.wav", "sine=frequency=300:beep_factor=1,volume=0.05", 6.0)
            loud = self._tone(folder, "l.wav", "sine=frequency=300,volume=0.8", 6.0)
            levels = []
            for name, src in (("q", quiet), ("l", loud)):
                out = folder / f"{name}.norm.wav"
                normalize_loudness(src, out)
                levels.append(measure_loudness(out).integrated)
            for level in levels:
                self.assertAlmostEqual(level, -14.0, delta=1.5)
            self.assertAlmostEqual(levels[0], levels[1], delta=1.0)


if __name__ == "__main__":
    unittest.main()


class PreviewColorTests(unittest.TestCase):
    """El fotograma de muestra enseña el color del acabado."""

    def test_the_colour_reaches_the_previewer_only_when_it_changes_something(self):
        from tests.fakes import make_studio

        studio, fakes = make_studio()
        studio.preview.frame("hola", {}, None, "tema", "9:16", None)
        studio.preview.frame("hola", {}, None, "tema", "9:16", {"look": "cine", "exposure": 0.3})
        self.assertIsNone(fakes.previewer.colors[0])
        self.assertEqual(fakes.previewer.colors[1].look, "cine")
        self.assertEqual(fakes.previewer.colors[1].exposure, 0.3)

    def test_a_wrong_look_is_refused(self):
        from tests.fakes import make_studio

        studio, _ = make_studio()
        with self.assertRaises(ValidationError):
            studio.preview.frame("hola", {}, None, "tema", "9:16", {"look": "sepia"})
