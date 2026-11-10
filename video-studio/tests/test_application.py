import unittest
from pathlib import Path

from app.application.consumers import EventConsumer
from app.domain.background import Background
from app.domain.errors import EngineError, NotFoundError, ValidationError, WriterError
from app.domain.events import SCRIPT_COMPLETED, SCRIPT_FAILED, SCRIPT_REQUESTED
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
        self.assertEqual(event.payload, {"topic": "gatos", "notes": "serio"})
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


if __name__ == "__main__":
    unittest.main()
