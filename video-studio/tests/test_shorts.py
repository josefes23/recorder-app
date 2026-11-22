"""Cortometrajes: diálogos con varias voces y la galería de música."""

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain.dialogue import Line, speakers_in, split_dialogue, spoken_text, validate_voices
from app.domain.errors import NotFoundError, ValidationError
from app.domain.music import duck_envelope, track_name, validate_volume, voiced_intervals
from app.infrastructure.music import FileMusicStore
from app.infrastructure.paths import Paths
from tests.fakes import DictCredentials, make_studio

SCRIPT = """NARRADOR: Era una mañana tranquila.
ANA: ¿Viste eso?
PEDRO: No vi nada.
Es que nadie mira.
ANA: Ahí.
Otra vez.
OJO: esto no es un personaje.
"""


class DialogueTests(unittest.TestCase):
    def test_finds_the_speakers_in_order_without_the_narrator(self):
        self.assertEqual(speakers_in(SCRIPT), ["ANA", "PEDRO", "OJO"])
        self.assertEqual(speakers_in("Sin etiquetas.\nNinguna."), [])
        self.assertEqual(speakers_in("ANA:\nnada"), [])  # etiqueta sin texto

    def test_only_known_speakers_take_a_line_the_rest_is_the_narrator(self):
        lines = split_dialogue(SCRIPT, {"ANA", "PEDRO"})
        self.assertEqual(lines, [
            Line("", "Era una mañana tranquila."),
            Line("ANA", "¿Viste eso?"),
            Line("PEDRO", "No vi nada."),
            Line("", "Es que nadie mira."),
            Line("ANA", "Ahí."),
            # «OJO» no tiene voz: la línea entera, etiqueta incluida, es del narrador.
            Line("", "Otra vez. OJO: esto no es un personaje."),
        ])
        self.assertTrue(spoken_text(lines).startswith("Era una mañana tranquila. ¿Viste eso?"))

    def test_without_speakers_it_is_one_narration(self):
        lines = split_dialogue("Hola.\n\nAdiós.", set())
        self.assertEqual(lines, [Line("", "Hola. Adiós.")])

    def test_voices_are_keyed_by_the_uppercase_label(self):
        self.assertEqual(validate_voices({"ana": "es-AR-ElenaNeural", "PEDRO": " es-MX-JorgeNeural ", "X": ""}),
                         {"ANA": "es-AR-ElenaNeural", "PEDRO": "es-MX-JorgeNeural"})
        self.assertEqual(validate_voices(None), {})
        with self.assertRaises(ValidationError):
            validate_voices({f"P{i}": "v" for i in range(9)})


class WriterForShortsTests(unittest.TestCase):
    def test_the_prompt_follows_the_length_and_the_dialogue(self):
        from app.domain.production import SHORT_FILM
        from app.domain.writer import DIALOGUE_RULE, SYSTEM_PROMPT, system_prompt

        self.assertIn("Entre 120 y 160 palabras", SYSTEM_PROMPT)
        self.assertIn("entre 45 y 60 segundos", SYSTEM_PROMPT)
        self.assertNotIn("MAYÚSCULAS", SYSTEM_PROMPT)

        short = system_prompt(SHORT_FILM, dialogue=True)
        self.assertIn("Escribes guiones para cortometrajes", short)
        self.assertIn("Entre 330 y 780 palabras", short)
        self.assertIn("entre 2 y 5 minutos", short)
        self.assertIn(DIALOGUE_RULE, short)
        self.assertIn("una intervención por línea", short)

    def test_a_dialogue_keeps_its_lines_and_labels(self):
        from app.domain.writer import validate_script

        raw = "<think>pienso</think>NARRADOR: **Era** de noche.\n\nANA: ¿Oíste?\nPEDRO:   No.  " + " palabra" * 60
        text = validate_script(raw, keep_lines=True)
        self.assertTrue(text.startswith("NARRADOR: Era de noche.\nANA: ¿Oíste?\nPEDRO: No."))
        self.assertEqual(speakers_in(text), ["ANA", "PEDRO"])

    def test_a_short_film_that_comes_back_like_a_reel_is_rejected(self):
        from app.domain.errors import WriterError

        studio, fakes = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="k"))
        fakes.composer.text = " ".join(["palabra"] * 120)
        with self.assertRaisesRegex(WriterError, "incompleto"):
            studio.scripts.write("gatos", "", "corto")
        self.assertIn("cortometrajes", fakes.composer.calls[-1][3])


class MusicDomainTests(unittest.TestCase):
    def test_track_names_are_plain_audio_files(self):
        self.assertEqual(track_name("/tmp/sub/Calma Total.MP3"), "Calma Total.MP3")
        for bad in ("", ".oculto.mp3", "foto.jpg", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                track_name(bad)

    def test_volume_goes_from_zero_to_one(self):
        self.assertEqual(validate_volume(0.25), 0.25)
        for bad in (-0.1, 1.5, True, "0.2"):
            with self.assertRaises(ValidationError):
                validate_volume(bad)

    def test_words_close_together_are_one_voiced_stretch(self):
        words = [{"start": 0.5, "end": 0.9}, {"start": 1.0, "end": 1.4}, {"start": 3.0, "end": 3.5}]
        self.assertEqual(voiced_intervals(words), [(0.5, 1.4), (3.0, 3.5)])

    def test_music_dips_under_the_voice_and_comes_back(self):
        points = duck_envelope([(2.0, 4.0)], 10.0, volume=0.5, ratio=0.4, ramp=0.5)
        self.assertEqual(points, [(0.0, 0.5), (1.5, 0.5), (2.0, 0.2), (4.0, 0.2), (4.5, 0.5), (10.0, 0.5)])
        times = [t for t, _ in points]
        self.assertEqual(times, sorted(set(times)))

    def test_voice_from_the_start_starts_ducked(self):
        points = duck_envelope([(0.0, 1.0)], 5.0, volume=0.5, ratio=0.4, ramp=0.3)
        self.assertEqual(points[0], (0.0, 0.2))
        self.assertEqual(points[-1], (5.0, 0.5))


def tone(path: Path, seconds: float, freq: float = 440.0) -> None:
    """Un tono de prueba en mp3, con el ffmpeg que trae moviepy: sin red ni ffmpeg del sistema."""
    import numpy as np
    from moviepy import AudioClip

    clip = AudioClip(lambda t: np.sin(2 * np.pi * freq * np.asarray(t))[..., None] * [0.5, 0.5], duration=seconds, fps=22050)
    clip.write_audiofile(str(path), fps=22050, logger=None)
    clip.close()


class FakeVoiceEngine:
    """Hace de motor: cada palabra dura 0,3 s y suena como un tono."""

    def __init__(self) -> None:
        self.voices: list[str] = []

    def synthesize_voice(self, text, voice, rate, pitch, out_mp3):
        self.voices.append(voice)
        words = text.split()
        tone(out_mp3, 0.3 * len(words))
        return [{"text": w, "start": 0.3 * i, "end": 0.3 * i + 0.25} for i, w in enumerate(words)]


class SoundtrackTests(unittest.TestCase):
    def test_each_turn_is_said_with_its_voice_and_the_marks_follow_the_joined_track(self):
        from moviepy import AudioFileClip

        from app.domain.dialogue import TURN_GAP
        from app.infrastructure.soundtrack import synthesize_dialogue

        engine = FakeVoiceEngine()
        lines = [Line("", "Era de noche."), Line("ANA", "¿Oíste eso ahí?"), Line("", "Nadie contestó.")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "voz.mp3"
            words = synthesize_dialogue(engine, lines, {"ANA": "elena"}, "dalia", "+0%", "+0Hz", out)
            with AudioFileClip(str(out)) as joined:
                total = joined.duration
            leftovers = sorted(p.name for p in Path(tmp).iterdir())

        self.assertEqual(engine.voices, ["dalia", "elena", "dalia"])
        self.assertEqual(leftovers, ["voz.mp3"])  # las partes se borran
        self.assertEqual(len(words), 8)
        # La primera palabra de Ana entra después de la narración y su silencio.
        self.assertGreaterEqual(words[3]["start"], 0.9 + TURN_GAP - 0.05)
        # Cada MP3 trae unas centésimas de relleno del codificador: la pista
        # unida dura algo más que la suma, nunca menos.
        expected = 0.9 + 0.9 + 0.6 + 2 * TURN_GAP
        self.assertGreaterEqual(total, expected - 0.05)
        self.assertLessEqual(total, expected + 0.4)

    def test_a_plain_script_is_one_call_like_before(self):
        from app.infrastructure.soundtrack import synthesize_dialogue

        engine = FakeVoiceEngine()
        with tempfile.TemporaryDirectory() as tmp:
            synthesize_dialogue(engine, [Line("", "Un reel normal.")], {}, "dalia", "+0%", "+0Hz", Path(tmp) / "v.mp3")
        self.assertEqual(engine.voices, ["dalia"])

    def test_music_loops_to_the_end_and_dips_under_the_voice(self):
        import numpy as np

        from app.infrastructure.soundtrack import music_bed

        with tempfile.TemporaryDirectory() as tmp:
            track = Path(tmp) / "musica.mp3"
            tone(track, 2.0, 220.0)
            bed = music_bed(track, 8.0, [{"start": 4.0, "end": 5.0}], volume=0.5)
            self.assertAlmostEqual(bed.duration, 8.0, delta=0.05)

            def loudness(start: float) -> float:
                samples = bed.to_soundarray(tt=np.linspace(start, start + 0.3, 600))
                return float(np.abs(samples).mean())

            quiet, under_voice = loudness(3.0), loudness(4.4)
            bed.close()
        self.assertGreater(quiet, 0.05)
        self.assertLess(under_voice, quiet * 0.6)


class MusicStoreTests(unittest.TestCase):
    def test_saves_lists_and_removes_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileMusicStore(Path(tmp) / "music")
            self.assertEqual(store.list(), [])
            self.assertEqual(store.save("calma.mp3", io.BytesIO(b"ID3...")), "calma.mp3")
            (Path(tmp) / "music" / "notas.txt").write_text("no es música", encoding="utf-8")
            self.assertEqual([t.name for t in store.list()], ["calma.mp3"])
            self.assertIsNotNone(store.path("calma.mp3"))
            self.assertIsNone(store.path("notas.txt"))
            store.remove("calma.mp3")
            self.assertEqual(store.list(), [])


class MusicApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.studio, self.fakes = make_studio()
        self.client = TestClient(create_app(Container(self.studio, Paths(tmp, tmp, tmp), workers=[])))

    def tearDown(self):
        self._tmp.cleanup()

    def test_upload_list_and_delete(self):
        response = self.client.post("/api/music/upload", files={"file": ("lluvia.mp3", b"ID3lluvia", "audio/mpeg")})
        self.assertEqual(response.json()["name"], "lluvia.mp3")
        names = [t["name"] for t in self.client.get("/api/music").json()["items"]]
        self.assertEqual(names, ["calma.mp3", "lluvia.mp3"])
        remaining = self.client.delete("/api/music/calma.mp3").json()["items"]
        self.assertEqual([t["name"] for t in remaining], ["lluvia.mp3"])

    def test_rejects_what_is_not_music_and_unknown_tracks(self):
        response = self.client.post("/api/music/upload", files={"file": ("foto.jpg", b"x", "image/jpeg")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete("/api/music/nada.mp3").status_code, 404)
        with self.assertRaises(NotFoundError):
            self.studio.music.file("nada.mp3")


class HorizontalFormatTests(unittest.TestCase):
    def test_a_horizontal_video_asks_for_horizontal_images(self):
        from app.domain.events import ILLUSTRATION_COMPLETED
        from app.domain.production import HORIZONTAL

        studio, fakes = make_studio(credentials=DictCredentials(CLOUDFLARE_ACCOUNT_ID="a", CLOUDFLARE_API_TOKEN="t"))
        event = studio.illustrations.request("Café", "una taza", review=False, format="16:9")
        self.assertEqual(event.payload["format"], "16:9")
        studio.illustrations.handle_request(event)
        self.assertTrue(fakes.events.by_key(event.key, (ILLUSTRATION_COMPLETED,)))
        self.assertEqual(fakes.illustrator.aspects, ["16:9"])
        self.assertIn(HORIZONTAL.framing, fakes.illustrator.calls[0][3])

    def test_unknown_formats_are_refused(self):
        studio, _ = make_studio(credentials=DictCredentials(CLOUDFLARE_ACCOUNT_ID="a", CLOUDFLARE_API_TOKEN="t"))
        with self.assertRaisesRegex(ValidationError, "Formato desconocido"):
            studio.illustrations.request("Café", "una taza", format="4:3")

    def test_cloudflare_turns_the_canvas_for_horizontal(self):
        from unittest import mock

        from app.domain.illustration import GeneratedImage
        from app.infrastructure.imaging import cloudflare

        with mock.patch.object(cloudflare.requests, "post") as post:
            post.return_value.ok = True
            post.return_value.headers = {"Content-Type": "image/jpeg"}
            post.return_value.content = b"\xff\xd8ok"
            try:
                cloudflare.paint("a", "t", "@cf/m", "una taza", 30, aspect="16:9")
            except Exception:  # noqa: BLE001 - solo interesa lo que se pidió
                pass
        form = post.call_args.kwargs["files"]
        self.assertEqual((form["width"][1], form["height"][1]), ("1536", "864"))
        self.assertIsInstance(GeneratedImage(b"x", ".jpg"), GeneratedImage)

    def test_the_cover_of_a_horizontal_video_is_a_youtube_thumbnail(self):
        studio, fakes = make_studio()
        studio.cover.paint("Hola", "impacto", None, "tema", "16:9")
        self.assertEqual(fakes.cover_painter.sizes[-1], (1280, 720))
        studio.cover.paint("Hola", "impacto", None, "tema")
        self.assertEqual(fakes.cover_painter.sizes[-1], (1080, 1920))

    def test_saved_videos_remember_their_format_inside_the_style(self):
        from app.domain.production import format_of

        self.assertEqual(format_of({"production": {"format": "16:9"}}).id, "16:9")
        self.assertEqual(format_of({}).id, "9:16")  # los de antes
        self.assertEqual(format_of({"production": {"format": "raro"}}).id, "9:16")


class StoryboardForShortsTests(unittest.TestCase):
    def test_a_reel_has_no_cap_and_a_short_film_keeps_its_own(self):
        from app.domain.production import REEL, SHORT_FILM
        from app.domain.storyboard import scene_range

        sentences = [f"Frase número {i} que dura un rato largo de decir en voz alta." for i in range(40)]
        self.assertIsNone(REEL.max_scenes)
        self.assertEqual(scene_range(sentences, REEL.max_scenes)[1], 40)
        self.assertEqual(scene_range(sentences, SHORT_FILM.max_scenes)[1], 30)

    def test_the_prompt_tells_where_the_faces_go(self):
        from app.domain.production import HORIZONTAL, VERTICAL
        from app.domain.storyboard import SYSTEM_PROMPT, system_prompt

        self.assertIn(VERTICAL.storyboard_rule, SYSTEM_PROMPT)
        self.assertIn("Reels, Shorts, TikTok", SYSTEM_PROMPT)
        horizontal = system_prompt(HORIZONTAL)
        self.assertIn(HORIZONTAL.storyboard_rule, horizontal)
        self.assertNotIn(VERTICAL.storyboard_rule, horizontal)

    def test_the_job_carries_length_and_format_to_the_writer(self):
        studio, fakes = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="k"))
        fakes.composer.text = '{"look": "acuarela", "characters": [], "scenes": [{"from": 1, "description": "una casa"}]}'
        event = studio.storyboards.request("Casa", "Una casa. Otra casa.", "", [], "corto", "16:9")
        studio.storyboards.handle_request(event)
        system, prompt = fakes.composer.calls[-1][3], fakes.composer.calls[-1][4]
        self.assertIn("cortometrajes en formato horizontal", system)
        self.assertIn("Escenas:", prompt)


class RenderProductionTests(unittest.TestCase):
    SCRIPT = "NARRADOR: Era de noche.\nANA: ¿Oíste eso?\nPEDRO: No.\n" + " palabra" * 10

    def test_production_travels_to_the_worker_and_is_kept_inside_the_style(self):
        from app.domain.scene import Scene

        studio, fakes = make_studio()
        production = {
            "format": "16:9", "length": "corto", "voices": {"ana": "es-AR-ElenaNeural", "PEDRO": "es-MX-JorgeNeural"},
            "music": "calma.mp3", "music_volume": 0.3, "ambient": True,
        }
        video_id, _ = studio.render.start(
            "Noche", self.SCRIPT, "es-MX-DaliaNeural", "+0%", "+0Hz", {"font_size": 64},
            [Scene("a.jpg", 0)], production=production,
        )
        spec = fakes.queue.enqueued[-1][1]
        self.assertEqual((spec.format, spec.music, spec.music_volume, spec.ambient), ("16:9", "calma.mp3", 0.3, True))
        self.assertEqual(spec.voices, {"ANA": "es-AR-ElenaNeural", "PEDRO": "es-MX-JorgeNeural"})
        # El diálogo conserva sus líneas para que el worker reparta las voces.
        self.assertTrue(spec.script.startswith("NARRADOR: Era de noche.\nANA: ¿Oíste eso?\nPEDRO: No."))
        self.assertEqual(spec.style, {"font_size": 64})  # el motor no ve la producción

        stored = fakes.videos.get(video_id)
        self.assertEqual(stored.style["font_size"], 64)
        self.assertEqual(stored.style["production"]["format"], "16:9")
        self.assertEqual(stored.style["production"]["length"], "corto")

    def test_without_production_it_is_a_vertical_reel_with_one_voice(self):
        from app.domain.scene import Scene

        studio, fakes = make_studio()
        studio.render.start("Reel", "Hola.\nAdiós. " + "palabra " * 10, "v", "+0%", "+0Hz", {}, [Scene(None, 0)])
        spec = fakes.queue.enqueued[-1][1]
        self.assertEqual((spec.format, spec.voices, spec.music, spec.ambient), ("9:16", {}, "", False))
        self.assertNotIn("\n", spec.script)

    def test_bad_production_is_refused_before_queueing(self):
        from app.domain.scene import Scene

        studio, fakes = make_studio()
        for bad in ({"format": "4:3"}, {"music": "foto.jpg"}, {"music_volume": 3}, {"length": "pelicula"}):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                studio.render.start("X", "Hola " * 20, "v", "+0%", "+0Hz", {}, [Scene(None, 0)], production=bad)
        self.assertEqual(fakes.queue.enqueued, [])


class DialogueSyncTests(unittest.TestCase):
    def test_scenes_of_a_dialogue_cut_where_the_voice_says_their_line(self):
        from app.domain.dialogue import split_dialogue, spoken_text
        from app.domain.scene import Scene, synced_to_voice
        from app.domain.script import WORDS_PER_SECOND, clean_script

        raw = "NARRADOR: Uno dos tres cuatro.\nANA: Cinco seis siete ocho.\nPEDRO: Nueve diez once doce."
        lines = split_dialogue(raw, {"ANA", "PEDRO"})
        spoken = spoken_text(lines).split()
        # La voz dice una palabra por segundo y no dice las etiquetas.
        words = [{"text": w, "start": float(i), "end": i + 0.8} for i, w in enumerate(spoken)]
        # La escena de Pedro se estimó en su etiqueta: palabra 10 del guion con etiquetas.
        estimated = 10 / WORDS_PER_SECOND
        synced = synced_to_voice([Scene("a.jpg", 0), Scene("b.jpg", estimated)], clean_script(raw), words)
        # «Nueve» es la palabra 8 de lo que se oye: entra entre «ocho» (7) y «nueve» (8).
        self.assertGreater(synced[1].start, 7.0)
        self.assertLessEqual(synced[1].start, 8.0)


class HorizontalFramingTests(unittest.TestCase):
    def test_a_vertical_image_in_a_horizontal_video_looks_up_where_the_faces_are(self):
        from app.domain.motion import crop_box

        left, top, right, bottom = crop_box((864, 1536), (1920, 1080), 1.0, (0.5, 0.5))
        self.assertAlmostEqual(right - left, 864)
        self.assertLess(top, 1536 * 0.15)  # arriba, no en el centro (que empezaría en 525)

    def test_same_shape_images_keep_their_focus(self):
        from app.domain.motion import crop_box

        self.assertEqual(crop_box((1080, 1920), (1080, 1920), 1.0, (0.5, 0.5)), (0.0, 0.0, 1080.0, 1920.0))
        _, top, _, _ = crop_box((1536, 864), (1920, 1080), 1.2, (0.5, 0.5))
        self.assertGreater(top, 0)  # centrado como siempre


class CustomLengthTests(unittest.TestCase):
    def test_segundos_a_medida(self):
        from app.domain.errors import ValidationError
        from app.domain.production import length_by_id

        short = length_by_id("45s")
        self.assertTrue(short.reel_like)
        self.assertEqual(short.seconds, (38, 52))
        self.assertIsNone(short.max_scenes)
        long = length_by_id("300s")
        self.assertFalse(long.reel_like)
        self.assertEqual(long.max_scenes, 30)
        self.assertGreater(long.words[0], 600)
        for bad in ("5s", "601s", "90", "1m"):
            with self.assertRaises(ValidationError):
                length_by_id(bad)


class PromptBookTests(unittest.TestCase):
    def test_los_originales_no_cambian_al_pasar_por_la_plantilla(self):
        from app.domain.prompts import PROMPTS, preview

        for spec in PROMPTS:
            result = preview(spec.id)
            self.assertTrue(result["examples"], spec.id)
            self.assertEqual(result["warnings"], [], spec.id)

    def test_editar_guardar_y_restaurar(self):
        from app.application.use_cases.prompts import PromptBook
        from app.domain.errors import ValidationError
        from app.domain.prompts import spec_by_id

        book = PromptBook()
        self.assertIsNone(book.template("image"))
        saved = book.save("image", "Dibuja: {description}\n{elements}\nEstilo {style}")
        self.assertTrue(saved["edited"])
        self.assertIn("Dibuja: Ana mira el móvil", saved["examples"][0]["text"])
        self.assertEqual(book.template("image"), "Dibuja: {description}\n{elements}\nEstilo {style}")
        # Guardar el original tal cual no cuenta como edición.
        self.assertFalse(book.save("image", spec_by_id("image").default)["edited"])
        self.assertIsNone(book.template("image"))
        book.save("image", "solo texto")
        self.assertIn("Falta {description}", book.preview("image", None)["warnings"][0])
        self.assertFalse(book.reset("image")["edited"])
        with self.assertRaises(ValidationError):
            book.save("image", "   ")
        with self.assertRaises(ValidationError):
            book.save("nada", "x")

    def test_el_guion_usa_la_edicion(self):
        from app.domain.production import REEL
        from app.domain.writer import system_prompt

        text = system_prompt(REEL, False, template="Escribe {words_min}-{words_max} palabras.\n{dialogue_rule}")
        self.assertEqual(text, "Escribe 120-160 palabras.")

    def test_el_prompt_editado_es_el_que_llega_al_modelo(self):
        studio, fakes = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="k"))
        fakes.composer.text = " ".join(["palabra"] * 120)
        studio.scripts._prompts.save("script", "Eres un guionista pirata. {words_min} palabras como mínimo.")
        studio.scripts.write("gatos", "", "reel")
        self.assertEqual(fakes.composer.calls[-1][3], "Eres un guionista pirata. 120 palabras como mínimo.")
