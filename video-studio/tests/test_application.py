import io
import unittest
from datetime import datetime
from pathlib import Path

from app.application.consumers import EventConsumer
from app.domain import review
from app.domain.background import Background
from app.domain.errors import EngineError, IllustratorError, NotFoundError, ValidationError, WriterError
from app.domain.events import (
    DESCRIPTION_COMPLETED,
    DESCRIPTION_FAILED,
    DESCRIPTION_REQUESTED,
    ILLUSTRATION_COMPLETED,
    ILLUSTRATION_FAILED,
    ILLUSTRATION_REQUESTED,
    REFERENCE_COMPLETED,
    REFERENCE_FAILED,
    REFERENCE_REQUESTED,
    SCRIPT_COMPLETED,
    SCRIPT_FAILED,
    SCRIPT_REQUESTED,
    STORYBOARD_COMPLETED,
    STORYBOARD_FAILED,
    STORYBOARD_REQUESTED,
    TITLES_COMPLETED,
    TITLES_FAILED,
    TITLES_REQUESTED,
)
from app.domain.illustration import DEFAULT_STYLE, Character, illustration_name
from app.domain.scene import Scene
from app.domain.video import RenderResult
from tests.fakes import LONG_SCRIPT, DictCredentials, FakeComposer, make_studio


class RenderTests(unittest.TestCase):
    def test_start_cleans_script_opens_record_and_enqueues(self):
        studio, f = make_studio()
        video_id, seconds = studio.render.start(
            "Tema", "**Hola** mundo " * 30, "voz", "+8%", "+0Hz", {"font_size": 80}, [Scene("a.mp4", 0)],
        )
        self.assertEqual(video_id, 1)
        self.assertEqual(seconds, 22.2)
        record = f.videos.get(1)
        self.assertEqual(record.script, ("Hola mundo " * 30).strip())
        self.assertEqual(record.status, "queued")
        (queued_id, spec), = f.queue.enqueued
        self.assertEqual(queued_id, 1)
        self.assertEqual(spec.scenes, [{"background": "a.mp4", "start": 0.0}])
        self.assertEqual(spec.output, "")  # la ruta la decide la cola

    def test_start_rejects_empty_script(self):
        studio, f = make_studio()
        with self.assertRaises(ValidationError):
            studio.render.start("t", "  ** ** ", "v", "+8%", "+0Hz", {}, [])
        self.assertEqual(f.queue.enqueued, [])

    def test_status_merges_record_and_live_progress(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        f.jobs.started(video_id)
        f.jobs.progressed(video_id, 0.4567, "Fotograma 3 de 9", "render")
        status = studio.render.status(video_id)
        self.assertEqual(status["status"], "running")
        self.assertEqual(status["progress"], 0.457)
        self.assertEqual(status["phase"], "render")
        self.assertEqual(status["topic"], "t")
        self.assertEqual([j["id"] for j in studio.render.active()], [video_id])

        f.jobs.finished(video_id, RenderResult("/out/x.mp4", 33.2, 4.1, 12))
        done = studio.render.status(video_id)
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["filename"], "/out/x.mp4")
        self.assertEqual(done["captions"], 12)
        self.assertEqual(studio.render.active(), [])

    def test_failed_job_keeps_detail(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        f.jobs.failed(video_id, "ffmpeg murió")
        status = studio.render.status(video_id)
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["error"], "ffmpeg murió")
        with self.assertRaises(NotFoundError):
            studio.render.status(99)
        self.assertIsNone(studio.jobs.status(99))

    def test_status_after_restart_comes_from_the_history(self):
        from app.application.render_jobs import RenderJobs
        from app.application.use_cases.render import RenderUseCases

        studio, f = make_studio()
        video_id, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        f.jobs.finished(video_id, RenderResult("/out/x.mp4", 33.0, 4.0, 10))

        # Un arranque nuevo: misma base, cola vacía.
        fresh = RenderUseCases(f.videos, f.queue, RenderJobs(f.videos))
        status = fresh.status(video_id)
        self.assertEqual(status["status"], "done")
        self.assertEqual(status["filename"], "/out/x.mp4")
        self.assertNotIn("progress", status)
        self.assertEqual(fresh.active(), [])


class ScriptTests(unittest.TestCase):
    def test_request_needs_topic_and_a_key(self):
        studio, f = make_studio()
        with self.assertRaises(ValidationError):
            studio.scripts.request(" ", "")
        with self.assertRaisesRegex(ValidationError, "clave"):
            studio.scripts.request("gatos", "")
        f.credentials.values["GEMINI_API_KEY"] = "g-key"
        event = studio.scripts.request("gatos", "serio")
        self.assertEqual(event.topic, SCRIPT_REQUESTED)
        self.assertEqual(event.payload, {"topic": "gatos", "notes": "serio", "length": "reel", "dialogue": False})
        self.assertEqual(studio.scripts.outcome(event.key), {"status": "pending"})

    def test_handle_request_writes_with_active_provider_and_publishes(self):
        creds = DictCredentials(SCRIPT_PROVIDER="deepseek", DEEPSEEK_API_KEY="d-key", DEEPSEEK_MODEL="deepseek-v4-pro")
        studio, f = make_studio(credentials=creds)
        event = studio.scripts.request("gatos", "")
        studio.scripts.handle_request(event)

        (provider, model, key, system, prompt), = f.composer.calls
        self.assertEqual((provider, model, key, prompt), ("deepseek", "deepseek-v4-pro", "d-key", "Tema: gatos"))
        self.assertIn("85 y 120 palabras", system)
        outcome = studio.scripts.outcome(event.key)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(outcome["script"], LONG_SCRIPT)
        self.assertEqual(outcome["seconds"], 33.3)

    def test_handle_request_is_idempotent_and_respects_claims(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n"))
        event = studio.scripts.request("gatos", "")
        studio.scripts.handle_request(event)
        studio.scripts.handle_request(event)  # redelivery tras un corte
        self.assertEqual(len(f.composer.calls), 1)

        other = studio.scripts.request("perros", "")
        f.events.claims.add(other.key)  # otro backend ya lo tiene
        studio.scripts.handle_request(other)
        self.assertEqual(len(f.composer.calls), 1)
        self.assertEqual(studio.scripts.outcome(other.key), {"status": "pending"})

    def test_failures_become_failed_events_with_a_readable_detail(self):
        studio, f = make_studio(
            credentials=DictCredentials(NVIDIA_API_KEY="n"),
            composer=FakeComposer(error=WriterError("La API key de NVIDIA no es válida.")),
        )
        event = studio.scripts.request("gatos", "")
        studio.scripts.handle_request(event)
        self.assertEqual(studio.scripts.outcome(event.key),
                         {"status": "failed", "detail": "La API key de NVIDIA no es válida."})

        short = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n"), composer=FakeComposer(text="muy corto"))
        studio2, _ = short
        event2 = studio2.scripts.request("gatos", "")
        studio2.scripts.handle_request(event2)
        self.assertIn("incompleto", studio2.scripts.outcome(event2.key)["detail"])

        crash = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n"), composer=FakeComposer(error=KeyError("choices")))
        studio3, _ = crash
        event3 = studio3.scripts.request("gatos", "")
        studio3.scripts.handle_request(event3)
        self.assertEqual(studio3.scripts.outcome(event3.key)["detail"], "KeyError: 'choices'")

    def test_template_and_estimate_are_local(self):
        studio, _ = make_studio()
        draft = studio.scripts.from_template("gatos")
        self.assertEqual(draft.script, "Hoy hablamos de gatos . Primera idea, segunda idea.")
        self.assertEqual(draft.seconds, 3.3)
        self.assertEqual(studio.scripts.estimate(LONG_SCRIPT).words, 90)

    def test_consumer_commits_after_each_event(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n"))
        consumer = EventConsumer(f.events, "scriptgen", (SCRIPT_REQUESTED,), studio.scripts.handle_request)
        a = studio.scripts.request("uno", "")
        b = studio.scripts.request("dos", "")
        offset = consumer.run_once(f.events.committed_offset("scriptgen"))
        self.assertEqual(offset, b.offset)
        self.assertEqual(f.events.committed_offset("scriptgen"), b.offset)
        self.assertEqual([e.topic for e in f.events.events],
                         [SCRIPT_REQUESTED, SCRIPT_REQUESTED, SCRIPT_COMPLETED, SCRIPT_COMPLETED])
        self.assertEqual(studio.scripts.outcome(a.key)["status"], "completed")
        # Sin nada nuevo, el offset no se mueve.
        self.assertEqual(consumer.run_once(offset), offset)
        self.assertNotIn(SCRIPT_FAILED, [e.topic for e in f.events.events])


class WriterSettingsTests(unittest.TestCase):
    def test_active_prefers_chosen_with_key_then_first_with_key(self):
        studio, f = make_studio(credentials=DictCredentials(SCRIPT_PROVIDER="google", DEEPSEEK_API_KEY="d"))
        self.assertEqual(studio.writer.active().id, "deepseek")
        self.assertEqual(studio.writer.label(), "DeepSeek · deepseek-v4-flash")
        f.credentials.values["GEMINI_API_KEY"] = "g"
        self.assertEqual(studio.writer.active().id, "google")
        self.assertIsNone(make_studio()[0].writer.label())

    def test_settings_shows_chosen_even_without_key(self):
        studio, _ = make_studio(credentials=DictCredentials(SCRIPT_PROVIDER="anthropic"))
        settings = studio.writer.settings()
        self.assertEqual(settings["provider"], "anthropic")
        self.assertIsNone(settings["label"])
        self.assertEqual([p["id"] for p in settings["providers"]], ["nvidia", "google", "deepseek", "anthropic"])
        self.assertEqual(settings["providers"][3]["key_hint"], None)
        self.assertEqual(settings["providers"][3]["models"][0]["id"], "claude-opus-5-5")
        self.assertEqual(make_studio()[0].writer.settings()["provider"], "nvidia")

    def test_save_keeps_existing_key_when_blank(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n-old"))
        result = studio.writer.save("nvidia", "", "meta/llama-3.3-70b-instruct")
        self.assertEqual(f.credentials.values["NVIDIA_API_KEY"], "n-old")
        self.assertEqual(f.credentials.values["SCRIPT_PROVIDER"], "nvidia")
        self.assertEqual(result["providers"][0]["key_hint"], "…-old")
        studio.writer.save("nvidia", " n-new ", "")
        self.assertEqual(f.credentials.values["NVIDIA_API_KEY"], "n-new")
        with self.assertRaises(ValidationError):
            studio.writer.save("openai")


class LibraryAndBackgroundsTests(unittest.TestCase):
    def test_delete_removes_file_and_record(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        f.jobs.finished(video_id, RenderResult("/out/x.mp4", 1.0, 1.0, 1))
        f.files.existing.add(Path("/out/x.mp4"))
        self.assertEqual(studio.library.file_of(video_id), Path("/out/x.mp4"))

        studio.library.delete(video_id)
        self.assertEqual(f.files.removed, [Path("/out/x.mp4")])
        self.assertEqual(studio.library.list(), [])
        with self.assertRaises(NotFoundError):
            studio.library.delete(video_id)

    def test_file_of_distinguishes_missing_record_from_missing_file(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        with self.assertRaisesRegex(NotFoundError, "todavía no tiene archivo"):
            studio.library.file_of(video_id)
        f.jobs.finished(video_id, RenderResult("/out/gone.mp4", 1.0, 1.0, 1))
        with self.assertRaisesRegex(NotFoundError, "ya no está en el disco"):
            studio.library.file_of(video_id)

    def test_upload_validates_extension(self):
        import io
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "no admitido: .txt"):
            studio.backgrounds.upload("notas.txt", io.BytesIO(b"x"))
        with self.assertRaisesRegex(ValidationError, "sin extensión"):
            studio.backgrounds.upload(None, io.BytesIO(b"x"))
        name, items = studio.backgrounds.upload("/tmp/sub/clip.MP4", io.BytesIO(b"abc"))
        self.assertEqual(name, "clip.MP4")
        self.assertEqual(f.backgrounds.saved, ["clip.MP4"])
        self.assertEqual(len(items), 2)

    def test_thumbnail_and_file_paths_or_not_found(self):
        studio, f = make_studio()
        self.assertEqual(studio.backgrounds.thumbnail("abc.jpg"), Path("/thumbs/abc.jpg"))
        with self.assertRaises(NotFoundError):
            studio.backgrounds.thumbnail("nope.jpg")
        self.assertEqual(studio.backgrounds.file("bosque_1.mp4"), Path("/bg/bosque_1.mp4"))
        with self.assertRaisesRegex(NotFoundError, "ya no está"):
            studio.backgrounds.file("nope.mp4")

    def test_delete_removes_the_file_and_refreshes_the_gallery(self):
        studio, f = make_studio()
        self.assertEqual(studio.backgrounds.delete("bosque_1.mp4"), [])
        self.assertEqual(f.backgrounds.removed, ["bosque_1.mp4"])
        with self.assertRaisesRegex(NotFoundError, "ya no está"):
            studio.backgrounds.delete("bosque_1.mp4")

    def test_search_names_clips_and_marks_the_ones_already_in_the_gallery(self):
        studio, f = make_studio()
        f.backgrounds.items.append(Background.describe("bosque_12.mp4", 9.0, 2_100_000, None))
        with self.assertRaisesRegex(ValidationError, "qué clips buscar"):
            studio.backgrounds.search("   ")

        clips = studio.backgrounds.search("  bosque ")
        self.assertEqual(f.stock.searched, ["bosque"])
        self.assertEqual(
            [(c.id, c.name, c.owned) for c in clips],
            [(11, "bosque_11.mp4", False), (12, "bosque_12.mp4", True)],
        )
        # La URL de descarga no sale a la interfaz: al bajar se resuelve por el id.
        self.assertNotIn("link", clips[0].as_dict())

    def test_download_saves_the_chosen_clips_and_reports_the_rest(self):
        studio, f = make_studio()
        f.backgrounds.items.append(Background.describe("bosque_12.mp4", 9.0, 2_100_000, None))

        report, items = studio.backgrounds.download("bosque", [11, 12, 11, 99])
        self.assertEqual(report.added, ["bosque_11.mp4"])
        self.assertEqual(report.existing, ["bosque_12.mp4"])
        self.assertEqual(report.failed, ["bosque_99.mp4: Pexels ya no tiene el clip 99."])
        self.assertEqual(f.backgrounds.saved, ["bosque_11.mp4"])  # una vez, aunque se marcara dos
        self.assertIn("bosque_11.mp4", [b.name for b in items])

    def test_download_with_nothing_saved_raises_the_first_reason(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "al menos un clip"):
            studio.backgrounds.download("bosque", [])
        f.stock.broken.add(11)
        with self.assertRaisesRegex(EngineError, "Sin conexión con Pexels"):
            studio.backgrounds.download("bosque", [11, 99])
        self.assertEqual(f.backgrounds.saved, [])

    def test_preview_normalizes_text_and_style(self):
        studio, f = make_studio()
        png = studio.preview.frame("  *hola* mundo ", {"font_size": 70}, "a.mp4", "")
        self.assertTrue(png.startswith(b"\x89PNG"))
        (text, style, background, topic), = f.previewer.calls
        self.assertEqual((text, style.font_size, background, topic), ("HOLA MUNDO", 70, "a.mp4", "preview"))
        studio.preview.frame("", None, None, "tema")
        self.assertEqual(f.previewer.calls[1][0], "TEXTO DE EJEMPLO")


class ImageSettingsTests(unittest.TestCase):
    def test_shows_the_ready_provider_and_masks_only_secrets(self):
        studio, _ = make_studio(credentials=DictCredentials(GEMINI_API_KEY="AIza-secret-1234"))
        settings = studio.images.settings()
        self.assertEqual(settings["provider"], "google")
        self.assertEqual(settings["label"], "Google · Nano Banana 2.1")
        self.assertEqual(settings["style"], DEFAULT_STYLE)
        cloudflare, google = settings["providers"]
        self.assertFalse(cloudflare["ready"])
        self.assertEqual([f["hint"] for f in cloudflare["fields"]], [None, None])
        self.assertTrue(google["ready"])
        self.assertEqual(google["fields"][0]["hint"], "…1234")

    def test_a_chosen_provider_only_takes_over_once_complete(self):
        studio, f = make_studio(credentials=DictCredentials(GEMINI_API_KEY="k"))
        saved = studio.images.save("cloudflare", "", {"CLOUDFLARE_ACCOUNT_ID": " acc-1 "})
        self.assertEqual(saved["provider"], "cloudflare")
        self.assertEqual(saved["label"], "Google · Nano Banana 2.1")  # aún le falta el token
        self.assertEqual(saved["providers"][0]["fields"][0]["hint"], "acc-1")  # el ID no es secreto

        saved = studio.images.save(
            "cloudflare", "@cf/black-forest-labs/flux-2-klein-9b", {"CLOUDFLARE_API_TOKEN": "tok-9999"},
        )
        self.assertEqual(saved["label"], "Cloudflare · FLUX.2 klein 9B")
        self.assertEqual(f.credentials.values["IMAGE_PROVIDER"], "cloudflare")
        # Un dato vacío conserva el guardado.
        studio.images.save("cloudflare", "", {"CLOUDFLARE_API_TOKEN": "  "})
        self.assertEqual(f.credentials.values["CLOUDFLARE_API_TOKEN"], "tok-9999")

    def test_save_rejects_unknown_provider_model_and_foreign_fields(self):
        studio, _ = make_studio()
        with self.assertRaisesRegex(ValidationError, "Generador desconocido"):
            studio.images.save("dalle")
        with self.assertRaisesRegex(ValidationError, "no ofrece"):
            studio.images.save("google", "flux")
        with self.assertRaisesRegex(ValidationError, "no usa GEMINI_API_KEY"):
            studio.images.save("cloudflare", "", {"GEMINI_API_KEY": "x"})


class IllustrationTests(unittest.TestCase):
    def test_request_publishes_job_with_resolved_provider_and_model(self):
        studio, f = make_studio(credentials=DictCredentials(GEMINI_API_KEY="k"))
        event = studio.illustrations.request(
            " Café ", "  una taza   humeante ", "acuarela", [{"name": "Ana", "traits": "pelo rojo"}], 7,
        )
        self.assertEqual(event.topic, ILLUSTRATION_REQUESTED)
        self.assertTrue(event.key.startswith("im-"))
        self.assertEqual(event.payload, {
            "topic": "Café", "description": "una taza humeante",
            "look": "acuarela", "characters": [{"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": None}],
            "seed": 7,
            "provider": "google", "model": "gemini-nano-banana-2.1",
            # Gemini también redacta y ve imágenes: revisa con su modelo del guion.
            "review": {"provider": "google", "model": "gemini-3.6-flash"},
            "format": "9:16",
        })

    def test_request_validates_before_publishing(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "ningún generador"):
            studio.illustrations.request("t", "algo")
        with self.assertRaisesRegex(ValidationError, "Describe"):
            studio.illustrations.request("t", "   ")
        with self.assertRaisesRegex(ValidationError, "nombre y sus rasgos"):
            studio.illustrations.request("t", "algo", characters=[{"name": "Ana"}])
        with self.assertRaisesRegex(ValidationError, "le falta id de cuenta y token de api"):
            studio.illustrations.request("t", "algo", provider_id="cloudflare")
        f.credentials.values["GEMINI_API_KEY"] = "k"
        with self.assertRaisesRegex(ValidationError, "no ofrece"):
            studio.illustrations.request("t", "algo", provider_id="google", model="dall-e")
        self.assertEqual(f.events.events, [])

    def test_handle_request_paints_saves_and_publishes_once(self):
        studio, f = make_studio(credentials=DictCredentials(GEMINI_API_KEY="k"))
        event = studio.illustrations.request("Café", "Ana sirve una taza", "", [{"name": "Ana", "traits": "pelo rojo"}], 7)
        studio.illustrations.handle_request(event)

        (provider, model, credentials, prompt, seed), = f.illustrator.calls
        self.assertEqual((provider, model, credentials), ("google", "gemini-nano-banana-2.1", {"GEMINI_API_KEY": "k"}))
        self.assertEqual(prompt.splitlines()[:3], ["Fotograma de película: Ana sirve una taza.", "Ana: pelo rojo.", f"Estilo: {DEFAULT_STYLE}."])
        self.assertEqual(seed, 7)

        name = illustration_name("Café", event.key, ".jpg")
        done = f.events.events[-1]
        self.assertEqual(done.topic, ILLUSTRATION_COMPLETED)
        self.assertEqual(done.payload["name"], name)
        self.assertEqual(f.backgrounds.saved, [name])
        self.assertEqual(studio.outcome(event.key)["name"], name)

        # Entregado otra vez tras un corte: no se repinta.
        studio.illustrations.handle_request(event)
        self.assertEqual(len(f.illustrator.calls), 1)

    def test_handle_request_publishes_the_failure_reason(self):
        studio, f = make_studio(credentials=DictCredentials(GEMINI_API_KEY="k"))
        f.illustrator.error = IllustratorError("cupo cero")
        event = studio.illustrations.request("t", "algo")
        studio.illustrations.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, ILLUSTRATION_FAILED)
        self.assertEqual(studio.outcome(event.key), {"status": "failed", "detail": "cupo cero"})
        self.assertEqual(f.backgrounds.saved, [])

    def test_competing_consumers_paint_each_image_once(self):
        studio, f = make_studio(credentials=DictCredentials(GEMINI_API_KEY="k"))
        for description in ("uno", "dos", "tres"):
            studio.illustrations.request("t", description)
        consumers = [
            EventConsumer(f.events, f"illustrator-{n}", (ILLUSTRATION_REQUESTED,), studio.illustrations.handle_request)
            for n in (1, 2)
        ]
        for consumer in consumers:
            consumer.run_once(0)
        self.assertEqual(len(f.illustrator.calls), 3)
        self.assertEqual(len(f.backgrounds.saved), 3)

    def test_outcome_is_pending_until_a_terminal_event(self):
        studio, _ = make_studio()
        self.assertEqual(studio.outcome("im-nada"), {"status": "pending"})


class ImageReviewTests(unittest.TestCase):
    """El modelo del guion mira cada imagen y se repinta lo que tenga fallos."""

    OK = '{"ok": true, "problems": []}'
    ARMS = '{"ok": false, "problems": ["Ana tiene tres brazos"]}'
    TEXT = '{"ok": false, "problems": ["hay letras en el cielo", "Ana tiene tres brazos"]}'

    def studio(self, *replies, **credentials):
        credentials = credentials or {"GEMINI_API_KEY": "g", "ANTHROPIC_API_KEY": "a", "SCRIPT_PROVIDER": "anthropic"}
        return make_studio(credentials=DictCredentials(**credentials), composer=FakeComposer(replies=list(replies)))

    def paint(self, studio, f, **request):
        event = studio.illustrations.request("Café", "Ana sirve una taza", seed=7, provider_id="google", **request)
        studio.illustrations.handle_request(event)
        return event, studio.outcome(event.key)

    def test_the_writer_reviews_with_the_image_and_the_description(self):
        studio, f = self.studio(self.OK)
        event, done = self.paint(studio, f)

        self.assertEqual(event.payload["review"], {"provider": "anthropic", "model": "claude-opus-5-5"})
        (provider, model, key, system, prompt), = f.composer.calls
        self.assertEqual((provider, model, key), ("anthropic", "claude-opus-5-5", "a"))
        self.assertIn("control de calidad", system)
        self.assertEqual(prompt, "Descripción de la escena: Ana sirve una taza")
        self.assertEqual(f.composer.images[0].data, b"\xff\xd8jpeg7")

        self.assertEqual(len(f.illustrator.calls), 1)
        self.assertEqual(done["review"], {
            "status": "approved", "reviewer": "Claude", "attempts": 1, "problems": [], "fixed": [], "detail": "",
        })

    def test_a_flagged_image_is_repainted_with_another_seed(self):
        studio, f = self.studio(self.ARMS, self.OK)
        _, done = self.paint(studio, f)

        self.assertEqual([call[4] for call in f.illustrator.calls], [7, 8])
        self.assertEqual(done["review"]["status"], "approved")
        self.assertEqual(done["review"]["attempts"], 2)
        self.assertEqual(done["review"]["fixed"], ["Ana tiene tres brazos"])
        # A la galería solo llega la buena.
        self.assertEqual(f.backgrounds.saved, [done["name"]])
        self.assertEqual(f.backgrounds.data[done["name"]], b"\xff\xd8jpeg8")

    def test_after_the_last_attempt_the_least_broken_one_stays(self):
        studio, f = self.studio(self.TEXT, self.ARMS, self.TEXT)
        _, done = self.paint(studio, f)

        self.assertEqual(len(f.illustrator.calls), review.MAX_ATTEMPTS)
        self.assertEqual(done["review"]["status"], "flagged")
        self.assertEqual(done["review"]["problems"], ["Ana tiene tres brazos"])
        self.assertEqual(f.backgrounds.data[done["name"]], b"\xff\xd8jpeg8")

    def test_no_new_attempt_once_the_request_is_too_old(self):
        studio, f = self.studio(self.ARMS, self.OK)
        event = studio.illustrations.request("Café", "Ana sirve una taza", seed=7, provider_id="google")
        late = datetime.fromisoformat(event.created_at) + review.RETRY_DEADLINE
        f.painter._clock = lambda: late
        studio.illustrations.handle_request(event)

        self.assertEqual(len(f.illustrator.calls), 1)
        self.assertEqual(studio.outcome(event.key)["review"]["status"], "flagged")

    def test_a_failed_review_never_sinks_the_image(self):
        for failure in (WriterError("Límite de peticiones alcanzado."), "no sé qué decir", RuntimeError("boom")):
            studio, f = self.studio(failure)
            _, done = self.paint(studio, f)
            self.assertEqual(done["status"], "completed")
            self.assertEqual(done["review"]["status"], "unchecked")
            self.assertTrue(done["review"]["detail"])
            self.assertEqual(len(f.illustrator.calls), 1)

    def test_if_repainting_fails_the_earlier_image_stays(self):
        studio, f = self.studio(self.ARMS)
        f.illustrator.error, f.illustrator.fail_from = IllustratorError("cupo agotado"), 1
        _, done = self.paint(studio, f)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["review"]["status"], "flagged")
        self.assertEqual(f.backgrounds.data[done["name"]], b"\xff\xd8jpeg7")

    def test_no_review_when_asked_not_to_or_when_the_writer_cannot_see(self):
        studio, f = self.studio()
        _, done = self.paint(studio, f, review=False)
        self.assertIsNone(done["review"])
        self.assertEqual(f.composer.calls, [])

        # DeepSeek redacta pero no ve imágenes.
        studio, f = self.studio(GEMINI_API_KEY="g", DEEPSEEK_API_KEY="d", SCRIPT_PROVIDER="deepseek")
        event, done = self.paint(studio, f)
        self.assertIsNone(event.payload["review"])
        self.assertIsNone(done["review"])
        self.assertEqual(f.composer.calls, [])


class CorrectionTests(unittest.TestCase):
    """Corregir una imagen de la galería: se edita esa, no se pinta otra."""

    CLOUDFLARE = {"CLOUDFLARE_ACCOUNT_ID": "acc", "CLOUDFLARE_API_TOKEN": "tok"}

    def studio(self, *replies, **extra):
        studio, f = make_studio(
            credentials=DictCredentials(**self.CLOUDFLARE, **extra), composer=FakeComposer(replies=list(replies)),
        )
        # Una imagen generada antes, ya en la galería.
        f.backgrounds.save("ia-cafe_1.jpg", io.BytesIO(b"\xff\xd8original"))
        return studio, f

    def test_request_needs_an_image_from_the_gallery_and_what_is_wrong(self):
        studio, f = self.studio()
        with self.assertRaisesRegex(ValidationError, "qué está mal"):
            studio.illustrations.request("Café", "Ana sirve", source="ia-cafe_1.jpg", correction="  ")
        with self.assertRaisesRegex(ValidationError, "Elige la imagen"):
            studio.illustrations.request("Café", "Ana sirve", correction="tiene tres brazos")
        with self.assertRaisesRegex(ValidationError, "clip de video"):
            studio.illustrations.request("Café", "", source="bosque_1.mp4", correction="sobra el árbol")
        with self.assertRaises(NotFoundError):
            studio.illustrations.request("Café", "", source="ia-borrada_9.jpg", correction="tiene tres brazos")
        with self.assertRaisesRegex(ValidationError, "demasiado larga"):
            studio.illustrations.request("Café", "", source="ia-cafe_1.jpg", correction="x" * 501)
        self.assertEqual(f.events.events, [])

    def test_the_description_is_optional_and_both_fields_travel_with_the_job(self):
        studio, f = self.studio()
        event = studio.illustrations.request(
            "Café", "", source=" ia-cafe_1.jpg ", correction="  tiene   tres brazos ", review=False,
        )
        self.assertEqual(event.topic, ILLUSTRATION_REQUESTED)
        self.assertEqual(event.payload["description"], "")
        self.assertEqual((event.payload["source"], event.payload["correction"]), ("ia-cafe_1.jpg", "tiene tres brazos"))

        # Un encargo normal no lleva esos campos.
        plain = studio.illustrations.request("Café", "Ana sirve")
        self.assertNotIn("source", plain.payload)

    def test_the_image_goes_first_and_the_library_references_after_it(self):
        studio, f = self.studio()
        saved = f.character_library.upsert(Character("Ana", "pelo rojo"))
        f.character_library.set_reference(saved.id, f.references.save("ref-1.jpg", b"cara de Ana"))
        cast = [{"name": "Ana", "traits": "pelo rojo", "saved": saved.id}]

        event = studio.illustrations.request(
            "Café", "Ana sirve una taza", "acuarela", cast, 7,
            source="ia-cafe_1.jpg", correction="Ana tiene seis dedos", review=False,
        )
        studio.illustrations.handle_request(event)

        (_, _, _, prompt, seed), = f.illustrator.calls
        self.assertEqual(f.illustrator.references, [[b"\xff\xd8original", b"cara de Ana"]])
        lines = prompt.splitlines()
        self.assertEqual(lines[0], "Corrige la primera imagen de referencia. Lo que hay que arreglar: Ana tiene seis dedos.")
        self.assertIn("La escena muestra: Ana sirve una taza.", lines)
        self.assertIn("Ana: pelo rojo.", lines)
        self.assertTrue(lines[-1].startswith("Ana se ve igual que en la segunda imagen de referencia"))
        self.assertEqual(seed, 7)

        # La corregida llega con nombre propio; la original sigue en la galería.
        done = studio.outcome(event.key)
        self.assertEqual(done["status"], "completed")
        self.assertNotEqual(done["name"], "ia-cafe_1.jpg")
        self.assertTrue(f.backgrounds.has("ia-cafe_1.jpg"))

    def test_the_reviewer_checks_the_fix_and_repaints_if_it_did_not_take(self):
        studio, f = self.studio(
            '{"ok": false, "problems": ["Ana sigue con seis dedos"]}', '{"ok": true}',
            ANTHROPIC_API_KEY="a", SCRIPT_PROVIDER="anthropic",
        )
        event = studio.illustrations.request(
            "Café", "Ana sirve una taza", seed=7, source="ia-cafe_1.jpg", correction="Ana tiene seis dedos",
        )
        studio.illustrations.handle_request(event)

        self.assertIn("Se pidió arreglar: Ana tiene seis dedos", f.composer.calls[0][4])
        # Cada intento edita la misma original, con otra semilla.
        self.assertEqual([call[4] for call in f.illustrator.calls], [7, 8])
        self.assertEqual([refs[0] for refs in f.illustrator.references], [b"\xff\xd8original"] * 2)
        self.assertEqual(studio.outcome(event.key)["review"]["fixed"], ["Ana sigue con seis dedos"])

    def test_an_image_deleted_before_its_turn_fails_with_the_reason(self):
        studio, f = self.studio()
        event = studio.illustrations.request("Café", "", source="ia-cafe_1.jpg", correction="sobra la taza")
        f.backgrounds.remove("ia-cafe_1.jpg")
        studio.illustrations.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, ILLUSTRATION_FAILED)
        self.assertIn("ya no está en la galería", studio.outcome(event.key)["detail"])
        self.assertEqual(f.illustrator.calls, [])


class StoryboardTests(unittest.TestCase):
    SCRIPT = "Jesús se bautizó en el Jordán. Hazlo tú también."
    ANSWER = (
        '{"look": "Fotografía cinematográfica", "characters": [{"name": "Jesús", "traits": "túnica crema"}], '
        '"scenes": [{"from": 1, "description": "Jesús entra en el río al amanecer"}]}'
    )

    def studio(self, answer: str = ANSWER):
        return make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer(answer))

    def test_request_needs_a_script_and_a_writer(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "guion"):
            studio.storyboards.request("t", "  ")
        with self.assertRaisesRegex(ValidationError, "Modelo del guion"):
            studio.storyboards.request("t", self.SCRIPT)
        self.assertEqual(f.events.events, [])

        studio, f = self.studio()
        event = studio.storyboards.request(" Bautismo ", self.SCRIPT, " acuarela ")
        self.assertEqual(event.topic, STORYBOARD_REQUESTED)
        self.assertTrue(event.key.startswith("sb-"))
        self.assertEqual(event.payload, {"topic": "Bautismo", "script": self.SCRIPT, "style": "acuarela", "characters": [], "length": "reel", "format": "9:16"})

    def test_handle_request_asks_the_writer_once_and_publishes_the_storyboard(self):
        studio, f = self.studio()
        event = studio.storyboards.request("Bautismo", self.SCRIPT, "acuarela")
        studio.storyboards.handle_request(event)

        (_, _, key, system, prompt), = f.composer.calls
        self.assertEqual(key, "nv")
        self.assertIn("director de arte", system)
        self.assertIn("1. (2 s) Jesús se bautizó en el Jordán.\n2. (1 s) Hazlo tú también.", prompt)

        done = studio.outcome(event.key)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["guide"]["characters"], [{"name": "Jesús", "traits": "túnica crema", "kind": "persona", "saved": None}])
        self.assertIsInstance(done["guide"]["seed"], int)
        self.assertEqual(done["scenes"], [{
            "start": 0.0, "text": self.SCRIPT, "description": "Jesús entra en el río al amanecer",
        }])
        self.assertEqual(f.events.events[-1].topic, STORYBOARD_COMPLETED)

        studio.storyboards.handle_request(event)
        self.assertEqual(len(f.composer.calls), 1)

    def test_a_bad_answer_fails_with_the_reason(self):
        studio, f = self.studio(answer="lo siento, no puedo")
        event = studio.storyboards.request("t", self.SCRIPT)
        studio.storyboards.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, STORYBOARD_FAILED)
        self.assertIn("formato esperado", studio.outcome(event.key)["detail"])


if __name__ == "__main__":
    unittest.main()


class CharacterLibraryTests(unittest.TestCase):
    """Elementos que se repiten entre videos, con su imagen de referencia."""

    CLOUDFLARE = {"CLOUDFLARE_ACCOUNT_ID": "acc", "CLOUDFLARE_API_TOKEN": "tok"}

    def studio(self, *replies, **extra):
        credentials = DictCredentials(**self.CLOUDFLARE, **extra)
        return make_studio(credentials=credentials, composer=FakeComposer(replies=list(replies)))

    def saved_with_reference(self, studio, f, name="Pincel", traits="robot de dibujo naranja", kind="objeto"):
        saved, event = studio.characters.save(name, traits, kind, "acuarela")
        studio.characters.handle_request(event)
        return f.character_library.get(saved.id)

    def test_save_keeps_it_and_orders_its_reference_image(self):
        studio, f = self.studio()
        saved, event = studio.characters.save(" Pincel ", " robot de dibujo naranja ", "objeto", " acuarela ")
        self.assertEqual((saved.name, saved.traits, saved.kind, saved.reference), ("Pincel", "robot de dibujo naranja", "objeto", None))
        self.assertEqual(event.topic, REFERENCE_REQUESTED)
        self.assertTrue(event.key.startswith("rf-"))
        self.assertEqual(event.payload, {
            "id": saved.id, "look": "acuarela", "provider": "cloudflare",
            "model": "@cf/black-forest-labs/flux-2-klein-4b", "review": None,
        })

        studio.characters.handle_request(event)
        (_, _, _, prompt, seed), = f.illustrator.calls
        self.assertTrue(prompt.startswith("Foto de producto de Pincel"))
        self.assertIn("Estilo: acuarela.", prompt)
        self.assertIsNone(seed)
        self.assertEqual(f.references.files, {"ref-1.jpg": b"\xff\xd8jpegNone"})
        self.assertEqual(f.character_library.get(saved.id).reference, "ref-1.jpg")
        done = studio.outcome(event.key)
        self.assertEqual((done["status"], done["id"], done["reference"]), ("completed", saved.id, "ref-1.jpg"))
        self.assertEqual(f.events.events[-1].topic, REFERENCE_COMPLETED)

        # Entregado otra vez: no se repinta.
        studio.characters.handle_request(event)
        self.assertEqual(len(f.illustrator.calls), 1)

    def test_saving_the_same_name_only_repaints_when_it_changed(self):
        studio, f = self.studio()
        first = self.saved_with_reference(studio, f)
        same, job = studio.characters.save("pincel", "robot de dibujo naranja", "objeto")
        self.assertIsNone(job)
        self.assertEqual((same.id, same.reference), (first.id, "ref-1.jpg"))

        changed, job = studio.characters.save("Pincel", "robot de dibujo azul", "objeto")
        self.assertEqual(changed.id, first.id)
        self.assertEqual(job.payload["id"], first.id)
        self.assertEqual(len(studio.characters.list()), 1)

    def test_the_reference_is_reviewed_like_any_scene(self):
        studio, f = self.studio(
            '{"ok": false, "problems": ["tiene tres manos"]}', '{"ok": true}',
            ANTHROPIC_API_KEY="a", SCRIPT_PROVIDER="anthropic",
        )
        saved, event = studio.characters.save("Ana", "pelo rojo", "persona")
        studio.characters.handle_request(event)
        self.assertEqual(len(f.illustrator.calls), 2)
        self.assertIn("Imagen de referencia de Ana", f.composer.calls[0][4])
        done = studio.outcome(event.key)
        self.assertEqual(done["review"]["fixed"], ["tiene tres manos"])
        self.assertTrue(f.illustrator.calls[0][3].startswith("Retrato de estudio de Ana"))

    def test_repaint_remove_and_failures(self):
        studio, f = self.studio()
        saved = self.saved_with_reference(studio, f)
        event = studio.characters.repaint(saved.id, "óleo")
        self.assertEqual(event.payload["look"], "óleo")

        studio.characters.remove(saved.id)
        self.assertEqual(studio.characters.list(), [])
        self.assertEqual(f.references.removed, ["ref-1.jpg"])
        with self.assertRaises(NotFoundError):
            studio.characters.repaint(saved.id)
        with self.assertRaises(NotFoundError):
            studio.characters.reference_file("ref-1.jpg")

        # Borrado antes de que llegara su referencia: el encargo falla con el motivo.
        studio.characters.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, REFERENCE_FAILED)
        self.assertIn("ya no está", studio.outcome(event.key)["detail"])

    def test_nothing_is_saved_without_a_name_traits_or_a_painter(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "ningún generador"):
            studio.characters.save("Ana", "pelo rojo")
        studio, f = self.studio()
        with self.assertRaisesRegex(ValidationError, "nombre y sus rasgos"):
            studio.characters.save("Ana", "  ")
        with self.assertRaisesRegex(ValidationError, "tipo desconocido"):
            studio.characters.save("Ana", "pelo rojo", "dragón")
        self.assertEqual(studio.characters.list(), [])

    def test_scenes_carry_the_reference_of_each_saved_element_they_name(self):
        studio, f = self.studio()
        pincel = self.saved_with_reference(studio, f)
        ana = self.saved_with_reference(studio, f, "Ana", "pelo rojo", "persona")
        f.illustrator.calls.clear(); f.illustrator.references.clear()

        cast = [
            {"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": ana.id},
            {"name": "Pincel", "traits": "robot de dibujo naranja", "kind": "objeto", "saved": pincel.id},
            {"name": "Luis", "traits": "barba negra"},
        ]
        event = studio.illustrations.request("t", "Luis mira cómo Pincel dibuja a Ana", "", cast, 5)
        studio.illustrations.handle_request(event)

        prompt = f.illustrator.calls[0][3]
        # En el orden del reparto: Ana primero, Pincel después; Luis no viene de la biblioteca.
        self.assertEqual(f.illustrator.references[0], [f.references.files["ref-2.jpg"], f.references.files["ref-1.jpg"]])
        self.assertIn("Ana se ve igual que en la primera imagen de referencia; Pincel, que en la segunda", prompt)
        self.assertNotIn("Luis se ve igual", prompt)

        # Una escena que no los nombra va sin referencias; uno borrado, también.
        studio.characters.remove(pincel.id)
        event = studio.illustrations.request("t", "Pincel dibuja solo", "", cast, 5)
        studio.illustrations.handle_request(event)
        self.assertEqual(f.illustrator.references[-1], [])
        self.assertNotIn("imagen de referencia", f.illustrator.calls[-1][3])

    def test_the_storyboard_keeps_what_is_in_the_video_and_leaves_the_library_alone(self):
        answer = (
            '{"look": "acuarela", "characters": ['
            '{"name": "ana", "kind": "persona", "traits": "otra"},'
            '{"name": "pincel", "kind": "objeto", "traits": "otro robot"},'
            '{"name": "Rex", "kind": "animal", "traits": "perro"}],'
            '"scenes": [{"from": 1, "description": "Pincel dibuja a Rex"}]}'
        )
        studio, f = make_studio(
            credentials=DictCredentials(**self.CLOUDFLARE, NVIDIA_API_KEY="nv"),
            composer=FakeComposer(answer),
        )
        studio.characters.save("Pincel", "robot de dibujo naranja", "objeto")
        studio.characters.save("Lucía", "mujer de 30 años", "persona")

        current = [{"name": "Ana", "traits": "pelo rojo", "kind": "persona"}, {"name": "Jesús", "traits": "túnica"}]
        event = studio.storyboards.request("t", "Pincel dibuja. Fin.", "acuarela", current)
        self.assertEqual(event.payload["characters"][0], {"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": None})
        studio.storyboards.handle_request(event)

        prompt = f.composer.calls[0][4]
        self.assertIn("Elementos que ya están en el video (mantén los que encajen):\n- Ana (persona): pelo rojo", prompt)
        # Lo guardado no se ofrece, ni siquiera Pincel, que el guion nombra: entra solo a mano.
        self.assertNotIn("robot de dibujo naranja", prompt)
        self.assertNotIn("Lucía", prompt)
        cast = studio.outcome(event.key)["guide"]["characters"]
        # El «pincel» del modelo coincide en nombre con el guardado, pero no se enlaza.
        self.assertEqual(cast, [
            {"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": None},
            {"name": "pincel", "traits": "otro robot", "kind": "objeto", "saved": None},
            {"name": "Rex", "traits": "perro", "kind": "animal", "saved": None},
        ])



class CoverTests(unittest.TestCase):
    TITLES = '{"titles": ["El *error* que cometes", "*3* trucos"]}'

    def test_paint_reads_the_title_and_finds_the_image(self):
        studio, f = make_studio()
        jpeg = studio.cover.paint("El *truco*", "franja", "bosque_1.mp4", "tema")
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        (words, design, background, topic), = f.cover_painter.calls
        self.assertEqual([(w.text, w.highlighted) for w in words], [("EL", False), ("TRUCO", True)])
        self.assertEqual((design, background, topic), ("franja", Path("/bg/bosque_1.mp4"), "tema"))

    def test_a_missing_image_paints_the_gradient_instead_of_failing(self):
        studio, f = make_studio()
        studio.cover.paint("Hola", "impacto", "borrada.jpg", "")
        _, _, background, topic = f.cover_painter.calls[0]
        self.assertIsNone(background)
        self.assertEqual(topic, "Hola")  # sin tema, el título da color al degradado

    def test_paint_rejects_an_empty_title_or_unknown_design(self):
        studio, f = make_studio()
        with self.assertRaises(ValidationError):
            studio.cover.paint("  ", "impacto", None, "t")
        with self.assertRaises(ValidationError):
            studio.cover.paint("Hola", "otro", None, "t")
        self.assertEqual(f.cover_painter.calls, [])

    def test_render_saves_the_cover_and_the_library_paints_it_again(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start(
            "Ayuno", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [Scene("bosque_1.mp4", 0)],
            cover={"title": "El *ayuno* real", "design": "titular", "background": "bosque_1.mp4"},
        )
        self.assertEqual(
            f.videos.get(video_id).cover,
            {"title": "El *ayuno* real", "design": "titular", "background": "bosque_1.mp4"},
        )
        jpeg, filename = studio.cover.of_video(video_id)
        self.assertIn(b"EL AYUNO REAL", jpeg)
        self.assertEqual(filename, "portada-ayuno.jpg")
        self.assertEqual(f.cover_painter.calls[-1][1:], ("titular", Path("/bg/bosque_1.mp4"), "Ayuno"))

    def test_videos_without_a_cover_get_the_default_one(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start(
            "ayuno intermitente", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [Scene("bosque_1.mp4", 0)],
            cover={"title": "   "},
        )
        self.assertEqual(f.videos.get(video_id).cover, {})
        studio.cover.of_video(video_id)
        words, design, background, _ = f.cover_painter.calls[-1]
        self.assertEqual([w.text for w in words if w.highlighted], ["INTERMITENTE"])
        self.assertEqual((design, background), ("impacto", Path("/bg/bosque_1.mp4")))
        with self.assertRaises(NotFoundError):
            studio.cover.of_video(99)

    def test_titles_need_something_to_read_and_a_writer(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "tema o el guion"):
            studio.cover.request_titles(" ", " ** ")
        with self.assertRaisesRegex(ValidationError, "Modelo del guion"):
            studio.cover.request_titles("ayuno", "")
        self.assertEqual(f.events.events, [])

    def test_titles_are_asked_once_and_published(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer(self.TITLES))
        event = studio.cover.request_titles(" ayuno ", "**El** guion.")
        self.assertEqual(event.topic, TITLES_REQUESTED)
        self.assertTrue(event.key.startswith("tt-"))
        self.assertEqual(event.payload, {"topic": "ayuno", "script": "El guion."})

        studio.cover.handle_request(event)
        studio.cover.handle_request(event)
        (_, _, key, system, prompt), = f.composer.calls
        self.assertEqual(key, "nv")
        self.assertIn("títulos de portada", system)
        self.assertIn("Guion del video:\nEl guion.", prompt)
        self.assertEqual(f.events.events[-1].topic, TITLES_COMPLETED)
        self.assertEqual(
            studio.outcome(event.key), {"status": "completed", "titles": ["El *error* que cometes", "*3* trucos"]},
        )

    def test_a_bad_answer_fails_with_the_reason(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer("{}"))
        event = studio.cover.request_titles("ayuno", "")
        studio.cover.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, TITLES_FAILED)
        self.assertIn("no propuso títulos", studio.outcome(event.key)["detail"])


class DescriptionTests(unittest.TestCase):
    TEXT = (
        "Qué dijo Jesús sobre Dios: tres enseñanzas de los evangelios que cambian cómo lo ves, "
        "contadas en menos de un minuto.\n\n#jesus #dios"
    )

    def test_request_needs_a_script_and_a_writer(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "guion"):
            studio.description.request("t", " ** ")
        with self.assertRaisesRegex(ValidationError, "Modelo del guion"):
            studio.description.request("t", "Un guion.")
        self.assertEqual(f.events.events, [])

    def test_it_is_written_once_with_the_script_and_the_plain_title(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer(self.TEXT))
        event = studio.description.request(" Jesús ", "**El** guion.", "Lo que *nadie* dice")
        self.assertEqual(event.topic, DESCRIPTION_REQUESTED)
        self.assertTrue(event.key.startswith("ds-"))
        self.assertEqual(event.payload, {"topic": "Jesús", "script": "El guion.", "title": "Lo que nadie dice"})

        studio.description.handle_request(event)
        studio.description.handle_request(event)
        (_, _, key, system, prompt), = f.composer.calls
        self.assertEqual(key, "nv")
        self.assertIn("palabras clave", system)
        self.assertIn("Título de la portada: Lo que nadie dice", prompt)
        self.assertEqual(f.events.events[-1].topic, DESCRIPTION_COMPLETED)
        self.assertEqual(studio.outcome(event.key), {"status": "completed", "description": self.TEXT})

    def test_a_short_answer_fails_with_the_reason(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer("Hola."))
        event = studio.description.request("t", "Un guion.")
        studio.description.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, DESCRIPTION_FAILED)
        self.assertIn("incompleta", studio.outcome(event.key)["detail"])

    def test_render_saves_the_description_cleaned(self):
        studio, f = make_studio()
        video_id, _ = studio.render.start(
            "t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [], description="  Hola   mundo \n\n\n\n#tag  ",
        )
        self.assertEqual(f.videos.get(video_id).description, "Hola mundo\n\n#tag")
        other, _ = studio.render.start("t", LONG_SCRIPT, "v", "+8%", "+0Hz", {}, [])
        self.assertEqual(f.videos.get(other).description, "")
