"""Transiciones entre escenas y entre los encuadres de una imagen fija."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain import transition as tr
from app.domain.errors import ValidationError
from app.domain.production import validate_production
from app.domain.scene import Scene, Span, checked_scenes, timeline_spans
from app.domain.transition import Blend, Change, Transition
from app.infrastructure.paths import Paths
from tests.fakes import make_studio

FADE = Transition(tr.CROSSFADE, 1.0)
LONG_SCRIPT = "palabra " * 90


class TransitionRulesTests(unittest.TestCase):
    def test_without_anything_it_is_the_dry_cut_of_always(self):
        self.assertEqual(tr.validate_transition(None), Transition(tr.CUT, tr.DEFAULT_SECONDS))
        self.assertEqual(tr.validate_transition({"kind": " Fundido ", "seconds": 1}), Transition(tr.CROSSFADE, 1.0))
        self.assertEqual(tr.validate_transition(FADE), FADE)

    def test_unknown_kinds_and_durations_out_of_range_are_refused(self):
        for bad in ({"kind": "estrella"}, {"kind": "fundido", "seconds": 0.1}, {"kind": "fundido", "seconds": 2},
                    {"kind": "fundido", "seconds": True}, {"kind": "fundido", "seconds": "1"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                tr.validate_transition(bad)

    def test_a_stored_one_that_no_longer_holds_is_ignored(self):
        self.assertIsNone(tr.read_transition(None))
        self.assertIsNone(tr.read_transition("fundido"))
        self.assertIsNone(tr.read_transition({"kind": "estrella"}))
        self.assertEqual(tr.read_transition({"kind": "negro", "seconds": 0.4}), Transition(tr.DIP, 0.4))

    def test_changes_are_centred_on_the_cut_and_never_longer_than_either_side(self):
        changes = tr.plan_changes([0.0, 5.0, 5.6, 10.0], [FADE, Transition(tr.CUT)])
        # Se recorta a lo que dura la escena corta (0,6 s): no se come la de al lado.
        self.assertEqual((changes[0].at, changes[0].kind), (5.0, tr.CROSSFADE))
        self.assertAlmostEqual(changes[0].seconds, 0.6)
        self.assertEqual(changes[1], Change(5.6))
        self.assertAlmostEqual(changes[0].start, 4.7)
        self.assertAlmostEqual(changes[0].end, 5.3)
        self.assertEqual(changes[1].start, changes[1].end)

    def test_two_transitions_in_a_row_never_overlap(self):
        bounds = [0.0, 3.0, 4.0, 7.0]
        changes = tr.plan_changes(bounds, [Transition(tr.SLIDE, 1.5), Transition(tr.ZOOM, 1.5)])
        self.assertLessEqual(changes[0].end, changes[1].start)

    def test_each_shot_is_painted_through_half_of_the_transitions_beside_it(self):
        bounds = [0.0, 4.0, 8.0, 10.0]
        changes = tr.plan_changes(bounds, [FADE, Transition(tr.CUT)])
        self.assertEqual(tr.reach(bounds, changes), [(0.0, 4.5), (3.5, 8.0), (8.0, 10.0)])
        self.assertEqual(tr.reach([0.0, 10.0], []), [(0.0, 10.0)])

    def test_moment_says_which_shot_shows_and_how_far_the_change_is(self):
        changes = [Change(4.0, tr.CROSSFADE, 1.0), Change(8.0)]
        self.assertEqual(tr.moment(changes, 3.4), (0, None))
        self.assertEqual(tr.moment(changes, 3.5), (0, Blend(tr.CROSSFADE, 0.0)))
        self.assertEqual(tr.moment(changes, 4.0), (0, Blend(tr.CROSSFADE, 0.5)))
        self.assertEqual(tr.moment(changes, 4.5), (1, None))
        # Un corte seco nunca mezcla.
        self.assertEqual(tr.moment(changes, 7.99), (1, None))
        self.assertEqual(tr.moment(changes, 8.0), (2, None))

    def test_each_kind_starts_on_the_old_shot_and_ends_on_the_new(self):
        for kind in (tr.CROSSFADE, tr.DIP, tr.SLIDE, tr.ZOOM):
            with self.subTest(kind=kind):
                first, last = tr.look(Blend(kind, 0.0)), tr.look(Blend(kind, 1.0))
                if kind == tr.SLIDE:
                    self.assertEqual((first.push, last.push), (0.0, 1.0))
                else:
                    self.assertEqual((first.alpha, last.alpha), (0.0, 1.0))
                    self.assertEqual((first.zoom_out, last.zoom_in), (1.0, 1.0))

    def test_dip_goes_through_black_and_zoom_is_closest_in_the_middle(self):
        self.assertAlmostEqual(tr.look(Blend(tr.DIP, 0.49)).gain_out, 0.02)
        self.assertAlmostEqual(tr.look(Blend(tr.DIP, 0.51)).gain_in, 0.02)
        middle = tr.look(Blend(tr.ZOOM, 0.5))
        self.assertAlmostEqual(middle.zoom_out, 1 + tr.ZOOM_DEPTH / 2)
        self.assertAlmostEqual(middle.zoom_in, 1 + tr.ZOOM_DEPTH / 2)
        self.assertAlmostEqual(middle.alpha, 0.5)


class SceneTransitionTests(unittest.TestCase):
    def test_a_scene_keeps_its_transition_and_without_one_stays_as_always(self):
        scene = Scene("a.jpg", 2.0, Transition(tr.DIP, 0.8))
        self.assertEqual(scene.as_dict(), {"background": "a.jpg", "start": 2.0, "transition": {"kind": "negro", "seconds": 0.8}})
        self.assertEqual(Scene.from_dict(scene.as_dict()), scene)
        self.assertEqual(Scene("a.jpg", 2.0).as_dict(), {"background": "a.jpg", "start": 2.0})
        self.assertEqual(Scene.from_dict({"background": "a.jpg", "transition": {"kind": "estrella"}}), Scene("a.jpg"))

    def test_spans_carry_the_transition_of_their_scene(self):
        spans = timeline_spans([Scene("a.jpg", 0), Scene("b.jpg", 4.0, FADE)], 10.0)
        self.assertEqual(spans, [Span("a.jpg", 0.0, 4.0), Span("b.jpg", 4.0, 10.0, FADE)])

    def test_scenes_from_the_interface_are_checked(self):
        self.assertEqual(checked_scenes([Scene("a.jpg"), Scene("b.jpg", 3, FADE)]), [Scene("a.jpg"), Scene("b.jpg", 3, FADE)])
        with self.assertRaises(ValidationError):
            checked_scenes([Scene("a.jpg", 0, Transition("estrella", 0.5))])

    def test_the_video_default_lives_in_the_production(self):
        self.assertEqual(validate_production({}).transition, Transition())
        self.assertEqual(validate_production({"transition": {"kind": "deslizar", "seconds": 0.6}}).transition,
                         Transition(tr.SLIDE, 0.6))
        with self.assertRaises(ValidationError):
            validate_production({"transition": {"kind": "fundido", "seconds": 3}})


class RenderTransitionTests(unittest.TestCase):
    def test_transitions_travel_to_the_worker_and_stay_with_the_video(self):
        studio, fakes = make_studio()
        video_id, _ = studio.render.start(
            "t", LONG_SCRIPT, "v", "+0%", "+0Hz", {}, [Scene("a.jpg", 0), Scene("b.jpg", 4, FADE)],
            production={"transition": {"kind": "negro", "seconds": 0.4}},
        )
        spec = fakes.queue.enqueued[-1][1]
        self.assertEqual(spec.transition, {"kind": "negro", "seconds": 0.4})
        self.assertEqual(spec.scenes[1]["transition"], {"kind": "fundido", "seconds": 1.0})
        stored = fakes.videos.get(video_id)
        self.assertEqual(stored.style["production"]["transition"], {"kind": "negro", "seconds": 0.4})
        self.assertNotIn("transition", stored.scenes[0])

    def test_a_bad_scene_transition_is_refused_before_queueing(self):
        studio, fakes = make_studio()
        with self.assertRaises(ValidationError):
            studio.render.start("t", LONG_SCRIPT, "v", "+0%", "+0Hz", {}, [Scene("a.jpg", 0, Transition("x", 0.5))])
        self.assertEqual(fakes.queue.enqueued, [])

    def test_the_api_takes_a_transition_per_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio, fakes = make_studio()
            client = TestClient(create_app(Container(studio, Paths(Path(tmp), Path(tmp), Path(tmp)), workers=[])))
            ok = client.post("/api/render", json={
                "topic": "t", "script": LONG_SCRIPT,
                "scenes": [{"background": "a.jpg", "start": 0}, {"background": "b.jpg", "start": 4,
                                                                  "transition": {"kind": "zoom", "seconds": 0.7}}],
                "production": {"transition": {"kind": "fundido", "seconds": 0.5}},
            })
            self.assertEqual(ok.status_code, 200)
            spec = fakes.queue.enqueued[-1][1]
            self.assertEqual(spec.scenes[1]["transition"], {"kind": "zoom", "seconds": 0.7})
            self.assertEqual(spec.transition, {"kind": "fundido", "seconds": 0.5})
            bad = client.post("/api/render", json={
                "topic": "t", "script": LONG_SCRIPT,
                "scenes": [{"background": "a.jpg", "start": 0, "transition": {"kind": "estrella"}}],
            })
            self.assertEqual(bad.status_code, 400)


def _solid(value: int, duration: float, size=(108, 192)):
    from moviepy import ColorClip

    return ColorClip(size, color=(value, value, value)).with_duration(duration)


class PaintingTests(unittest.TestCase):
    def setUp(self):
        import numpy as np

        self.black = np.zeros((4, 6, 3), np.uint8)
        self.white = np.full((4, 6, 3), 255, np.uint8)

    def test_crossfade_mixes_and_dip_passes_through_black(self):
        from app.infrastructure.transitions import blend_frames

        self.assertEqual(int(blend_frames(Blend(tr.CROSSFADE, 0.5), self.black, self.white).mean()), 128)
        self.assertEqual(int(blend_frames(Blend(tr.DIP, 0.5), self.white, self.white).max()), 0)
        self.assertEqual(int(blend_frames(Blend(tr.DIP, 1.0), self.black, self.white).min()), 255)

    def test_slide_pushes_the_old_shot_out_to_the_left(self):
        from app.infrastructure.transitions import blend_frames

        frame = blend_frames(Blend(tr.SLIDE, 0.5), self.black, self.white)
        self.assertEqual(frame.shape, (4, 6, 3))
        self.assertEqual((int(frame[:, :3].max()), int(frame[:, 3:].min())), (0, 255))

    def test_the_track_is_the_shot_itself_outside_the_changes(self):
        from app.infrastructure.transitions import chain

        changes = [Change(2.0, tr.CROSSFADE, 1.0)]
        track = chain([(0.0, _solid(0, 2.5)), (1.5, _solid(200, 2.5))], changes, 4.0)
        self.assertEqual(track.duration, 4.0)
        self.assertEqual(int(track.get_frame(1.0).max()), 0)
        self.assertEqual(int(track.get_frame(2.0).mean()), 100)
        self.assertEqual(int(track.get_frame(3.0).min()), 200)


class TrackTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image, ImageDraw

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        image = Image.new("RGB", (432, 768), "white")
        draw = ImageDraw.Draw(image)
        for x in range(0, 432, 24):
            draw.line((x, 0, x, 768), fill="black")
        image.save(self.dir / "ia-x_1.jpg")
        (self.dir / "clip.mp4").write_bytes(b"no es un video")

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_background_is_painted_through_half_of_its_transitions(self):
        from app.infrastructure import render_worker

        built = []
        gen = SimpleNamespace(
            WIDTH=108, HEIGHT=192, IMAGE_EXTS={".jpg"},
            build_background=lambda path, topic, duration: built.append(("bg", duration)) or _solid(200, duration),
        )

        def moving(path, duration, size, seed, transition):
            built.append(("mov", duration, transition))
            return _solid(0, duration)

        scenes = [{"background": "ia-x_1.jpg", "start": 0}, {"background": "clip.mp4", "start": 3}]
        with mock.patch.object(render_worker, "emit"), mock.patch.object(render_worker, "moving_image", side_effect=moving):
            track = render_worker.build_track(gen, self.dir, scenes, "t", 6.0, Transition(tr.CROSSFADE, 1.0))
        # La imagen se pinta medio segundo de más y el clip, medio de menos al principio.
        self.assertEqual(built, [("mov", 3.5, Transition(tr.CROSSFADE, 1.0)), ("bg", 3.5)])
        self.assertAlmostEqual(track.duration, 6.0)
        self.assertEqual(int(track.get_frame(2.0).max()), 0)
        self.assertEqual(int(track.get_frame(3.0).mean()), 100)
        self.assertEqual(int(track.get_frame(4.0).min()), 200)

    def test_a_scene_transition_beats_the_video_default(self):
        from app.infrastructure import render_worker

        seen = []
        gen = SimpleNamespace(WIDTH=108, HEIGHT=192, IMAGE_EXTS={".jpg"}, build_background=None)
        with mock.patch.object(render_worker, "emit"), mock.patch.object(
            render_worker, "moving_image", side_effect=lambda p, d, size, seed, t: seen.append(t) or _solid(0, d),
        ):
            render_worker.build_track(gen, self.dir, [
                {"background": "ia-x_1.jpg", "start": 0},
                {"background": "ia-x_1.jpg", "start": 3, "transition": {"kind": "zoom", "seconds": 0.6}},
            ], "t", 6.0, FADE)
        self.assertEqual(seen, [FADE, Transition(tr.ZOOM, 0.6)])

    def test_a_still_image_changes_framing_with_its_transition(self):
        from app.infrastructure.motion import moving_image

        def jumps(clip):
            # Cuánto cambia la imagen entre dos fotogramas seguidos, a 30 fps.
            frames = [clip.get_frame(t / 30).astype(int) for t in range(80, 100)]
            return max(abs(a - b).mean() for a, b in zip(frames, frames[1:]))

        cut = moving_image(self.dir / "ia-x_1.jpg", 6.0, (108, 192), seed=1)
        fade = moving_image(self.dir / "ia-x_1.jpg", 6.0, (108, 192), seed=1, transition=FADE)
        # Con corte, el cambio de encuadre del segundo 3 es un salto; con
        # fundido se reparte en un segundo de fotogramas.
        self.assertGreater(jumps(cut), 3 * jumps(fade))
        self.assertTrue((cut.get_frame(1.0) == fade.get_frame(1.0)).all())


if __name__ == "__main__":
    unittest.main()
