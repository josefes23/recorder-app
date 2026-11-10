import unittest

from app.domain import background, events, script, stock, style, video, writer
from app.domain.captions import clip_to_duration
from app.domain.errors import WriterError
from app.domain.scene import Scene, Span, timeline_spans


class ScriptTests(unittest.TestCase):
    def test_clean_strips_markdown_and_collapses_spaces(self):
        self.assertEqual(script.clean_script("  **Hola**   _mundo_ # [x] `y`  "), "Hola mundo x y")
        self.assertEqual(script.clean_script(None), "")

    def test_estimate_uses_words_per_second(self):
        text = " ".join(["palabra"] * 27)
        self.assertAlmostEqual(script.estimate_seconds(text), 10.0)
        result = script.estimate(" ".join(["palabra"] * 100))
        self.assertEqual(result.words, 100)
        self.assertEqual(result.seconds, 37.0)
        self.assertTrue(result.in_range)
        self.assertFalse(script.estimate("corto").in_range)


class StyleTests(unittest.TestCase):
    def test_from_dict_fills_defaults_and_casts(self):
        s = style.CaptionStyle.from_dict({"font_size": "70", "animate": 0, "extra": 1})
        self.assertEqual(s.font_size, 70)
        self.assertFalse(s.animate)
        self.assertEqual(s.stroke, 8)
        self.assertEqual(style.CaptionStyle.from_dict(None).as_dict(), style.DEFAULT_STYLE)

    def test_autofit_floor_never_exceeds_requested_size(self):
        self.assertEqual(style.CaptionStyle(font_size=92).min_font_size, 52)
        self.assertEqual(style.CaptionStyle(font_size=40).min_font_size, 40)


class SceneTests(unittest.TestCase):
    def test_spans_sort_force_first_to_zero_and_cover_duration(self):
        spans = timeline_spans([Scene("b.mp4", 3.0), Scene("a.mp4", 0.5), Scene(None, 1.0)], 10.0)
        self.assertEqual(spans, [Span("a.mp4", 0.0, 3.0), Span("b.mp4", 3.0, 10.0)])
        self.assertEqual(spans[1].duration, 7.0)

    def test_spans_skip_empty_and_clip_to_duration(self):
        self.assertEqual(timeline_spans([], 10.0), [])
        self.assertEqual(timeline_spans([Scene(None, 0)], 10.0), [])
        spans = timeline_spans([Scene("a.mp4", 0), Scene("b.mp4", 12.0)], 10.0)
        self.assertEqual(spans, [Span("a.mp4", 0.0, 10.0)])
        spans = timeline_spans([Scene("a.mp4", 0), Scene("b.mp4", 0.01)], 10.0)
        self.assertEqual(spans, [Span("b.mp4", 0.01, 10.0)])

    def test_scene_from_dict_tolerates_missing_values(self):
        self.assertEqual(Scene.from_dict({"background": "", "start": None}), Scene(None, 0.0))
        self.assertEqual(Scene.from_dict(None), Scene())


class CaptionTests(unittest.TestCase):
    def test_clip_drops_late_blocks_and_trims_last(self):
        captions = [
            {"start": 0.0, "duration": 2.0, "text": "a"},
            {"start": 2.0, "duration": 5.0, "text": "b"},
            {"start": 9.0, "duration": 1.0, "text": "c"},
        ]
        kept = clip_to_duration(captions, 5.0)
        self.assertEqual([c["text"] for c in kept], ["a", "b"])
        self.assertEqual(kept[1]["duration"], 3.0)
        self.assertEqual(captions[1]["duration"], 5.0)  # no muta la entrada
        self.assertEqual(clip_to_duration([], 5.0), [])


class BackgroundTests(unittest.TestCase):
    def test_kind_group_and_support(self):
        self.assertTrue(background.is_supported("clip.MP4"))
        self.assertFalse(background.is_supported("notas.txt"))
        self.assertFalse(background.is_supported(None))
        self.assertEqual(background.kind_of("foto.png"), "image")
        self.assertEqual(background.kind_of("clip.mov"), "video")
        self.assertEqual(background.group_of("bosque_12"), "bosque")
        self.assertEqual(background.group_of("bosque"), "bosque")

    def test_describe_builds_the_card(self):
        item = background.Background.describe("mar_2.mp4", 8.0, 1_250_000, "x.jpg")
        self.assertEqual(item.as_dict(), {
            "name": "mar_2.mp4", "stem": "mar_2", "group": "mar", "kind": "video",
            "duration": 8.0, "size_mb": 1.2, "thumb": "x.jpg",
        })


class StockTests(unittest.TestCase):
    def test_clip_name_follows_the_generator_scheme_so_the_gallery_groups_it(self):
        self.assertEqual(stock.clip_name("Dormir Bien!", 42), "dormir-bien_42.mp4")
        self.assertEqual(stock.clip_name("¿?", 1), "bg_1.mp4")
        self.assertEqual(background.group_of("dormir-bien_42"), "dormir-bien")

    def test_best_vertical_prefers_the_smallest_at_target_width_under_the_cap(self):
        def v(w, h, size):
            return stock.Variant(w, h, size, f"https://cdn/{w}x{h}")

        self.assertIsNone(stock.best_vertical([v(1920, 1080, 5)]))
        self.assertEqual(stock.best_vertical([v(720, 1280, 2), v(1080, 1920, 6), v(2160, 3840, 40)]).width, 1080)
        # Sin ninguna que llegue a 1080 de ancho, la más ancha que haya.
        self.assertEqual(stock.best_vertical([v(540, 960, 1), v(720, 1280, 2)]).width, 720)
        # Las que pasan del tope se descartan, salvo que no quede otra.
        self.assertEqual(stock.best_vertical([v(1080, 1920, 200), v(720, 1280, 2)], max_bytes=100).width, 720)
        self.assertEqual(stock.best_vertical([v(1080, 1920, 200)], max_bytes=100).width, 1080)
        # Para reproducir una muestra vale la más ligera, aunque no llegue a 1080.
        self.assertEqual(stock.smallest_vertical([v(1080, 1920, 6), v(720, 1280, 2), v(1920, 1080, 1)]).width, 720)
        self.assertIsNone(stock.smallest_vertical([v(1920, 1080, 1)]))

    def test_as_dict_keeps_the_download_link_private_but_shares_the_sample(self):
        clip = stock.StockClip(1, "p", 10, 1080, 1920, 3.0, "Ana", "u", play="muestra", link="secreto", name="x_1.mp4")
        data = clip.as_dict()
        self.assertNotIn("link", data)
        self.assertEqual((data["name"], data["owned"], data["play"]), ("x_1.mp4", False, "muestra"))


class VideoTests(unittest.TestCase):
    def test_slugify_and_output_name(self):
        self.assertEqual(video.slugify("¡Hola, Mundo! 2026"), "hola-mundo-2026")
        self.assertEqual(video.slugify(""), "video")
        self.assertEqual(video.output_filename("Café con leche", "20260101_1200"), "caf-con-leche_20260101_1200.mp4")

    def test_render_spec_round_trip(self):
        spec = video.RenderSpec("t", "s", "v", "+8%", "+0Hz", {"a": 1}, [{"background": "x"}], "/out.mp4")
        self.assertEqual(video.RenderSpec.from_dict(spec.as_dict()), spec)
        self.assertEqual(video.RenderSpec.from_dict({}).scenes, [])


class EventTests(unittest.TestCase):
    def test_outcome_follows_topic_suffix(self):
        self.assertEqual(events.outcome_of("script.completed"), "completed")
        self.assertEqual(events.outcome_of("script.failed"), "failed")
        self.assertEqual(events.outcome_of("script.requested"), "pending")

    def test_job_keys_are_unique_and_prefixed(self):
        a, b = events.new_job_key(), events.new_job_key()
        self.assertTrue(a.startswith("sc-") and b.startswith("sc-"))
        self.assertNotEqual(a, b)


class WriterTests(unittest.TestCase):
    def test_prompt_includes_notes_only_when_present(self):
        self.assertEqual(writer.build_prompt("gatos", "  "), "Tema: gatos")
        self.assertIn("Indicaciones adicionales:\nen tono serio", writer.build_prompt("gatos", "en tono serio\n"))

    def test_validate_strips_reasoning_and_rejects_broken_output(self):
        good = "<think>pensando</think>" + " ".join(["palabra"] * 60)
        self.assertEqual(writer.validate_script(good).split().__len__(), 60)
        with self.assertRaises(WriterError):
            writer.validate_script("")
        with self.assertRaisesRegex(WriterError, "incompleto \\(3 palabras\\)"):
            writer.validate_script("muy corto esto")

    def test_label_and_mask(self):
        nvidia = writer.provider_by_id("NVIDIA ")
        self.assertEqual(writer.short_label(nvidia, "meta/llama-3.3-70b-instruct"), "NVIDIA · llama-3.3-70b-instruct")
        self.assertEqual(writer.short_label(writer.provider_by_id("anthropic"), "x"), "Claude")
        self.assertIsNone(writer.provider_by_id("openai"))
        self.assertEqual(writer.mask_key("sk-abcdef"), "…cdef")
        self.assertIsNone(writer.mask_key(None))


if __name__ == "__main__":
    unittest.main()
