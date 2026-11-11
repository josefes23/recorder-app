import json
import unittest

from datetime import datetime, timedelta

from app.domain import (
    background,
    events,
    illustration,
    motion,
    review,
    saved_characters,
    script,
    stock,
    storyboard,
    style,
    video,
    writer,
)
from app.domain.captions import clip_to_duration
from app.domain.errors import ValidationError, WriterError
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


class IllustrationTests(unittest.TestCase):
    SENTENCE = "Una frase de prueba con nueve palabras en total."

    def test_plan_groups_whole_sentences_into_six_second_scenes(self):
        # 6 frases × 9 palabras = 54 palabras ≈ 20 s → 3 escenas de dos frases.
        beats = illustration.plan_beats(" ".join([self.SENTENCE] * 6))
        self.assertEqual([b.start for b in beats], [0.0, 6.7, 13.3])
        self.assertEqual(beats[0].text, f"{self.SENTENCE} {self.SENTENCE}")
        self.assertEqual(beats[0].as_dict(), {"start": 0.0, "text": beats[0].text})

    def test_plan_caps_scenes_and_handles_short_or_empty_scripts(self):
        long = " ".join(f"Frase número {i} con algo más de texto aquí." for i in range(40))
        self.assertEqual(len(illustration.plan_beats(long)), illustration.MAX_SCENES)
        self.assertEqual(illustration.plan_beats("   "), [])
        self.assertEqual(illustration.plan_beats("**Hola.**"), [illustration.Beat(0.0, "Hola.")])

    def test_opening_marks_stay_with_their_sentence(self):
        self.assertEqual(
            illustration.split_sentences("¿Sabías esto? ¡Increíble! Y más…  Fin."),
            ["¿Sabías esto?", "¡Increíble!", "Y más…", "Fin."],
        )

    JESUS = illustration.Character("Jesús", "hombre de unos treinta años, túnica de lino crema")
    JUAN = illustration.Character("Juan el Bautista", "hombre enjuto, piel de camello")

    def test_prompt_puts_the_scene_first_then_who_appears_style_and_framing(self):
        guide = illustration.VisualGuide("acuarela suave.", (self.JESUS, self.JUAN), 7)
        prompt = illustration.image_prompt("  jesus entra en el río  al amanecer ", guide)
        self.assertEqual(prompt.splitlines(), [
            "Fotograma de película: jesus entra en el río al amanecer.",
            "Jesús: hombre de unos treinta años, túnica de lino crema.",
            "Estilo: acuarela suave.",
            illustration.FRAMING,
        ])

    def test_prompt_never_quotes_or_forbids(self):
        # FLUX.2 no admite prompts negativos y escribe lo que va entre comillas.
        prompt = illustration.image_prompt("una hucha llena")
        self.assertNotIn("«", prompt)
        self.assertNotIn("Sin ", prompt)
        self.assertIn(f"Estilo: {illustration.DEFAULT_STYLE}.", prompt)

    def test_cast_matches_whole_names_without_accents_or_case(self):
        cast = (self.JESUS, self.JUAN)
        self.assertEqual(illustration.cast_in("JESÚS y Juan el bautista hablan", cast), cast)
        self.assertEqual(illustration.cast_in("Juan pesca", cast), ())
        self.assertEqual(illustration.cast_in("los jesuitas", cast), ())

    def test_guide_is_validated_and_drops_empty_rows(self):
        guide = illustration.validate_guide(
            "  óleo  ", [{"name": " Ana ", "traits": " pelo rojo "}, {"name": "", "traits": " "}], 5,
        )
        self.assertEqual(guide, illustration.VisualGuide("óleo", (illustration.Character("Ana", "pelo rojo"),), 5))
        self.assertEqual(guide.as_dict()["characters"], [{"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": None}])
        for look, cast, seed, message in (
            ("x" * 801, [], None, "estilo"),
            ("", [{"name": "Ana"}], None, "nombre y sus rasgos"),
            ("", [{"name": "Ana", "traits": "a"}, {"name": "ANA", "traits": "b"}], None, "dos elementos"),
            ("", [{"name": f"P{i}", "traits": "t"} for i in range(7)], None, "Como mucho 6"),
            ("", [{"name": "Rex", "traits": "perro", "kind": "dragón"}], None, "tipo desconocido"),
            ("", [{"name": "Rex", "traits": "perro", "saved": "3"}], None, "biblioteca"),
            ("", [{"name": "Rex", "traits": "perro", "saved": True}], None, "biblioteca"),
            ("", [], -1, "semilla"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValidationError, message):
                illustration.validate_guide(look, cast, seed)

    def test_name_groups_by_topic_and_is_stable_per_job(self):
        name = illustration.illustration_name("Café y Finanzas", "im-deadbeef00", ".jpg")
        self.assertEqual(name, "ia-cafe-y-finanzas_3735928559.jpg")
        self.assertEqual(background.group_of(name.removesuffix(".jpg")), "ia-cafe-y-finanzas")
        self.assertTrue(illustration.new_illustration_key().startswith("im-"))

    def test_description_is_required_and_bounded(self):
        self.assertEqual(illustration.validate_description("  dos   palabras "), "dos palabras")
        with self.assertRaises(ValidationError):
            illustration.validate_description("   ")
        with self.assertRaises(ValidationError):
            illustration.validate_description("x" * 1501)

    def test_providers(self):
        cloudflare = illustration.image_provider_by_id(" CLOUDFLARE ")
        self.assertEqual(cloudflare.default_model, "@cf/black-forest-labs/flux-2-klein-4b")
        self.assertTrue(cloudflare.has_model("@cf/black-forest-labs/flux-2-klein-9b"))
        self.assertFalse(cloudflare.has_model("gemini-nano-banana-2.1"))
        self.assertIsNone(illustration.image_provider_by_id("dalle"))



class StoryboardTests(unittest.TestCase):
    BEATS = [illustration.Beat(0.0, "Jesús se bautizó."), illustration.Beat(6.3, "Hazlo tú también.")]

    def answer(self, **overrides) -> str:
        data = {
            "look": "Fotografía cinematográfica, luz dorada",
            "characters": [{"name": "Jesús", "traits": "pelo castaño, túnica crema"}],
            "scenes": [{"n": 1, "description": "Jesús entra en el Jordán"}, {"n": 2, "description": "Una mujer sonríe"}],
        }
        data.update(overrides)
        return json.dumps(data, ensure_ascii=False)

    def test_prompt_numbers_each_scene_and_carries_style_and_script(self):
        prompt = storyboard.build_prompt("Bautismo", "", "Jesús se bautizó. Hazlo tú también.", self.BEATS)
        self.assertIn("Tema: Bautismo", prompt)
        self.assertIn(f"Estilo que pide el usuario: {illustration.DEFAULT_STYLE}", prompt)
        self.assertIn("Escenas (2):\n1. Jesús se bautizó.\n2. Hazlo tú también.", prompt)
        self.assertIn('"scenes"', storyboard.SYSTEM_PROMPT)

    def test_parse_reads_guide_and_keeps_timing_from_the_beats(self):
        board = storyboard.parse_storyboard(self.answer(), self.BEATS, seed=9)
        self.assertEqual(board.guide.look, "Fotografía cinematográfica, luz dorada")
        self.assertEqual(board.guide.characters, (illustration.Character("Jesús", "pelo castaño, túnica crema"),))
        self.assertEqual(board.guide.seed, 9)
        self.assertEqual(board.scenes[1], storyboard.StoryboardScene(6.3, "Hazlo tú también.", "Una mujer sonríe"))
        self.assertEqual(board.as_dict()["scenes"][0]["description"], "Jesús entra en el Jordán")

    def test_parse_tolerates_fences_reasoning_and_numbers_as_text(self):
        raw = "<think>pienso</think>```json\n" + self.answer(scenes=[
            {"n": "2", "description": "dos"}, {"n": "1", "description": "uno"},
        ]) + "\n```"
        board = storyboard.parse_storyboard(raw, self.BEATS, seed=1)
        self.assertEqual([s.description for s in board.scenes], ["uno", "dos"])

    def test_parse_drops_broken_or_repeated_characters_and_caps_the_cast(self):
        cast = [{"name": "Ana", "traits": "a"}, {"name": "ana", "traits": "b"}, {"name": "Sin rasgos"}, "basura"]
        cast += [{"name": f"P{i}", "traits": "t"} for i in range(8)]
        board = storyboard.parse_storyboard(self.answer(characters=cast), self.BEATS, seed=1)
        self.assertEqual([c.name for c in board.guide.characters], ["Ana", "P0", "P1", "P2", "P3", "P4"])

    def test_prompt_lists_the_fixed_cast_and_the_library(self):
        fixed = [illustration.Character("Lucía", "mujer de 30 años", "persona", 3)]
        offered = [illustration.Character("Pincel", "robot de dibujo naranja", "objeto", 7)]
        prompt = storyboard.build_prompt("t", "", "Hola. Adiós.", self.BEATS, fixed, offered)
        self.assertIn("Elementos que ya están en el video (mantén los que encajen):\n- Lucía (persona): mujer de 30 años", prompt)
        self.assertIn("Elementos guardados de otros videos (usa los que encajen):\n- Pincel (objeto): robot de dibujo naranja", prompt)
        bare = storyboard.build_prompt("t", "", "Hola. Adiós.", self.BEATS)
        self.assertNotIn("ya están en el video", bare)
        self.assertNotIn("guardados", bare)
        for word in ('"kind"', "animal", "objeto", "lugar", "elementos guardados"):
            self.assertIn(word, storyboard.SYSTEM_PROMPT)

    def test_parse_keeps_what_the_model_reuses_exactly_as_it_was(self):
        current = (
            illustration.Character("Lucía", "mujer de 30 años", "persona", 3),
            # De otro video: el modelo lo deja fuera y no se fuerza.
            illustration.Character("Jesús", "túnica crema", "persona", 9),
        )
        offered = (illustration.Character("Pincel", "robot de dibujo naranja", "objeto", 7),)
        cast = [
            {"name": "LUCIA", "kind": "persona", "traits": "otra mujer"},
            # El modelo reescribe lo de la biblioteca: manda la biblioteca.
            {"name": "pincel", "kind": "persona", "traits": "un robot cualquiera"},
            {"name": "Firulais", "kind": "animal", "traits": "perro salchicha"},
            {"name": "La mesa", "kind": "dragón", "traits": "mesa de roble"},
        ]
        board = storyboard.parse_storyboard(self.answer(characters=cast), self.BEATS, 1, current, offered)
        self.assertEqual(board.guide.characters, (
            current[0],
            offered[0],
            illustration.Character("Firulais", "perro salchicha", "animal"),
            illustration.Character("La mesa", "mesa de roble", "persona"),
        ))

    def test_parse_rejects_what_cannot_be_painted(self):
        for raw, message in (
            ("no es json", "formato esperado"),
            ("[1, 2]", "formato esperado"),
            (self.answer(look=" "), "sin estilo"),
            (self.answer(scenes=[{"n": 1, "description": "uno"}]), "faltan 1 de 2"),
        ):
            with self.subTest(raw=raw[:20]), self.assertRaisesRegex(WriterError, message):
                storyboard.parse_storyboard(raw, self.BEATS, seed=1)

    def test_seed_fits_in_32_bits(self):
        self.assertTrue(all(0 < storyboard.new_seed() < 2**31 for _ in range(50)))


if __name__ == "__main__":
    unittest.main()


class ReviewTests(unittest.TestCase):
    def test_parse_review_reads_the_verdict_and_trims_the_problems(self):
        self.assertEqual(review.parse_review('{"ok": true, "problems": []}'), review.Review(True))
        # Envuelto en ```json y con razonamiento delante, como lo devuelven algunos modelos.
        raw = '<think>miro</think>```json\n{"ok": false, "problems": ["  la mujer   tiene una tercera mano ", "", 3]}\n```'
        self.assertEqual(review.parse_review(raw), review.Review(False, ("la mujer tiene una tercera mano",)))
        many = json.dumps({"ok": False, "problems": [f"fallo {n}" for n in range(9)] + ["x " * 200]})
        problems = review.parse_review(many).problems
        self.assertEqual(len(problems), review.MAX_PROBLEMS)
        long = review.parse_review(json.dumps({"ok": False, "problems": ["palabra " * 60]})).problems[0]
        self.assertLessEqual(len(long), review.PROBLEM_LIMIT + 1)
        self.assertTrue(long.endswith("…"))

    def test_when_the_reviewer_changes_its_mind_the_last_verdict_counts(self):
        raw = (
            '{"ok": false, "problems": ["dos lápices"]}\n\nRevisando de nuevo: la mano es suya.\n\n'
            '{"ok": true, "problems": []}'
        )
        self.assertEqual(review.parse_review(raw), review.Review(True))
        raw = '{"ok": true, "problems": []} Mirando mejor: {"nota": 1} {"ok": false, "problems": ["tres manos"]}'
        self.assertEqual(review.parse_review(raw), review.Review(False, ("tres manos",)))

    def test_a_silent_rejection_still_counts_and_garbage_is_an_error(self):
        self.assertEqual(review.parse_review('{"ok": false}'), review.Review(False, (review.UNEXPLAINED,)))
        for raw in ("", "parece bien", '{"ok": "sí"}', "[1, 2]"):
            with self.assertRaisesRegex(WriterError, "formato esperado"):
                review.parse_review(raw)

    def test_each_attempt_gets_its_own_seed(self):
        self.assertEqual([review.retry_seed(7, n) for n in range(3)], [7, 8, 9])
        self.assertEqual(review.retry_seed(2**32 - 1, 1), 0)
        self.assertIsNone(review.retry_seed(None, 2))

    def test_retries_stop_at_the_cap_or_the_deadline(self):
        start = datetime(2026, 11, 10, 12, 0, 0)
        self.assertTrue(review.may_retry(1, start, start + timedelta(seconds=30)))
        self.assertFalse(review.may_retry(review.MAX_ATTEMPTS, start, start))
        self.assertFalse(review.may_retry(1, start, start + review.RETRY_DEADLINE))

    def test_report_keeps_the_approved_one_or_the_least_broken(self):
        bad = review.Review(False, ("tres brazos", "letras"))
        worse = review.Review(False, ("tres brazos", "letras", "dos cabezas"))
        good = review.Review(True)

        approved = review.report("Claude", [bad, good])
        self.assertEqual(review.pick([bad, good]), 1)
        self.assertEqual(approved.as_dict(), {
            "status": "approved", "reviewer": "Claude", "attempts": 2,
            "problems": [], "fixed": ["tres brazos", "letras"], "detail": "",
        })

        flagged = review.report("Claude", [worse, bad, review.Review(False, ("letras", "otra"))])
        self.assertEqual(review.pick([worse, bad, review.Review(False, ("a", "b"))]), 1)
        self.assertEqual((flagged.status, flagged.problems, flagged.attempts), ("flagged", ("tres brazos", "letras"), 3))

        self.assertEqual(review.unchecked("Claude", 1, "sin saldo").as_dict()["status"], "unchecked")

    def test_review_prompt_and_rules(self):
        self.assertEqual(review.review_prompt("  Ana   sirve café "), "Descripción de la escena: Ana sirve café")
        for rule in ("Anatomía", "fundidos", "Letras", "JSON"):
            self.assertIn(rule, review.SYSTEM_PROMPT)

    def test_only_providers_that_see_images_can_review(self):
        seers = {p.id for p in writer.PROVIDERS if p.sees_images}
        self.assertEqual(seers, {"google", "anthropic"})
        self.assertEqual(illustration.GeneratedImage(b"", ".png").media_type, "image/png")
        self.assertEqual(illustration.GeneratedImage(b"", ".raro").media_type, "image/jpeg")


class ReferenceTests(unittest.TestCase):
    ANA = illustration.Character("Ana", "pelo rojo", "persona", 1)
    LUIS = illustration.Character("Luis", "barba negra", "persona", 2)
    PINCEL = illustration.Character("Pincel", "robot de dibujo naranja", "objeto", 3)

    def test_reference_line_says_which_image_is_whose_by_ordinal(self):
        self.assertEqual(
            illustration.reference_line([self.ANA]),
            "Ana se ve igual que en la imagen de referencia: mismo aspecto (cara, pelo, ropa, forma y colores), "
            "en la postura y el lugar que pide la escena.",
        )
        line = illustration.reference_line([self.ANA, self.LUIS, self.PINCEL])
        self.assertTrue(line.startswith(
            "Ana se ve igual que en la primera imagen de referencia; Luis, que en la segunda; Pincel, que en la tercera:"
        ))
        self.assertNotIn("imagen 0", line)
        self.assertNotIn("imagen 1", line)

    def test_image_prompt_puts_the_references_after_the_cast(self):
        guide = illustration.VisualGuide("acuarela", (self.ANA, self.PINCEL), 1)
        lines = illustration.image_prompt("Ana enciende a Pincel", guide, [self.ANA, self.PINCEL]).splitlines()
        self.assertEqual(lines[1:3], ["Ana: pelo rojo.", "Pincel: robot de dibujo naranja."])
        self.assertTrue(lines[3].startswith("Ana se ve igual que en la primera imagen de referencia; Pincel"))
        self.assertTrue(lines[4].startswith("Estilo: acuarela"))
        self.assertNotIn("referencia", illustration.image_prompt("Ana enciende a Pincel", guide))

    def test_each_kind_gets_its_own_reference_framing(self):
        for kind, start in (
            ("persona", "Retrato de estudio de Ana"),
            ("animal", "Foto de referencia de Ana: el animal entero"),
            ("objeto", "Foto de producto de Ana"),
            ("lugar", "Plano general de Ana"),
        ):
            prompt = saved_characters.reference_prompt(illustration.Character("Ana", "pelo rojo", kind), "acuarela")
            self.assertTrue(prompt.startswith(start), kind)
            self.assertEqual(prompt.splitlines()[1:], ["Ana: pelo rojo.", "Estilo: acuarela."])
        self.assertIn(illustration.DEFAULT_STYLE, saved_characters.reference_prompt(self.ANA))
        self.assertEqual(set(saved_characters.REFERENCE_FRAMING), set(illustration.KINDS))

    def test_reference_names_never_leave_the_folder(self):
        self.assertEqual(saved_characters.reference_name(12, ".png"), "ref-12.png")
        self.assertTrue(saved_characters.is_reference_name("ref-12.jpg"))
        for bad in ("../ref-1.jpg", "ref-1.exe", "ref-a.jpg", "ia-cafe_1.jpg", "", "ref-1.jpg/.."):
            self.assertFalse(saved_characters.is_reference_name(bad), bad)

    def test_saved_character_turns_into_a_cast_member_with_its_id(self):
        saved = saved_characters.SavedCharacter(4, "Pincel", "robot", "objeto", "ref-4.jpg", "a", "b")
        self.assertEqual(saved.as_character(), illustration.Character("Pincel", "robot", "objeto", 4))
        self.assertEqual(saved.as_dict()["reference"], "ref-4.jpg")


class MotionTests(unittest.TestCase):
    def test_scenes_are_cut_into_shots_of_three_to_four_seconds(self):
        for duration, count in ((2.0, 1), (4.0, 1), (4.5, 1), (5.0, 2), (6.0, 2), (8.0, 2), (8.5, 3), (12.0, 3), (40.0, 10)):
            shots = motion.plan_shots(duration, seed=1)
            self.assertEqual(len(shots), count, duration)
            self.assertAlmostEqual(sum(s.duration for s in shots), duration)
            self.assertAlmostEqual(shots[-1].end, duration)
            if count > 1:
                self.assertTrue(all(motion.MIN_SHOT_SECONDS <= s.duration <= motion.MAX_SHOT_SECONDS for s in shots))
        self.assertEqual(motion.plan_shots(0), [])

    def test_wide_first_then_close_and_medium_to_alternating_sides(self):
        shots = motion.plan_shots(14.0, seed=3)
        self.assertEqual([s.zoom_from for s in shots], [motion.WIDE, motion.CLOSE, motion.MEDIUM, motion.CLOSE])
        self.assertEqual(shots[0].focus_from, (0.5, 0.5))
        sides = [s.focus_from[0] - 0.5 for s in shots[1:]]
        self.assertTrue(all(a * b < 0 for a, b in zip(sides, sides[1:])), sides)
        self.assertTrue(all(s.focus_from[1] == motion.FOCUS_Y for s in shots[1:]))
        self.assertEqual(motion.plan_shots(14.0, seed=3), shots)

    def test_zoom_goes_in_continuously_and_jumps_at_each_cut(self):
        shots = motion.plan_shots(6.0, seed=1)
        zooms = [motion.camera_at(shots, t / 10)[0] for t in range(0, 30)]
        self.assertEqual(zooms, sorted(zooms))
        self.assertAlmostEqual(motion.camera_at(shots, 3.0 - 1e-6)[0] - motion.camera_at(shots, 0)[0], 0.06, places=4)
        before, after = motion.camera_at(shots, 3.0 - 1e-6)[0], motion.camera_at(shots, 3.0)[0]
        self.assertGreater(after / before, 1.10)  # se lee como corte, no como tropiezo
        self.assertEqual(motion.camera_at(shots, 99), motion.camera_at(shots, 6.0))

    def test_the_crop_keeps_the_frame_shape_and_never_leaves_the_image(self):
        for source in ((864, 1536), (1920, 1080), (1000, 1000)):
            for t in (0, 1.5, 2.99, 3.0, 5.99):
                for seed in range(5):
                    zoom, fx, fy = motion.camera_at(motion.plan_shots(6.0, seed), t)
                    left, top, right, bottom = motion.crop_box(source, (1080, 1920), zoom, (fx, fy))
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(right, source[0] + 1e-6)
                    self.assertLessEqual(bottom, source[1] + 1e-6)
                    self.assertAlmostEqual((right - left) / (bottom - top), 1080 / 1920, places=6)
        # Zoom 1: la imagen entera si ya tiene la forma del cuadro.
        self.assertEqual(motion.crop_box((864, 1536), (1080, 1920), 1.0, (0.5, 0.5)), (0, 0, 864, 1536))
        # Un foco pegado al borde se queda dentro.
        self.assertEqual(motion.crop_box((864, 1536), (1080, 1920), 2.0, (0.0, 0.0))[:2], (0, 0))

    def test_each_scene_gets_its_own_stable_seed(self):
        self.assertEqual(motion.scene_seed(2, "ia-cafe_1.jpg"), motion.scene_seed(2, "ia-cafe_1.jpg"))
        self.assertNotEqual(motion.scene_seed(1, "ia-cafe_1.jpg"), motion.scene_seed(2, "ia-cafe_1.jpg"))

