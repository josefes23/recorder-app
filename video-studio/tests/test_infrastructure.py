import base64
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import requests

from app.domain.errors import EngineError, IllustratorError
from app.domain.illustration import Character, GeneratedImage, image_provider_by_id
from app.domain.video import NewVideo, VideoStatus
from app.domain.writer import provider_by_id
from app.infrastructure import ffmpeg
from app.infrastructure.backgrounds import FileBackgroundStore
from app.infrastructure.env_credentials import EnvCredentials, merge_env_lines
from app.infrastructure.imaging import cloudflare, gemini, sniff_extension
from app.infrastructure.imaging.illustrator import HttpIllustrator
from app.infrastructure.llm import openai_compatible, vision
from app.infrastructure.llm.composer import GOOGLE, HttpScriptComposer
from app.infrastructure.pexels import ClipStream, parse_video
from app.infrastructure.references import FileReferenceStore
from app.infrastructure.sqlite import Database, SqliteCharacterRepository, SqliteEventLog, SqliteVideoRepository


class EnvCredentialsTests(unittest.TestCase):
    def test_merge_replaces_removes_and_appends(self):
        lines = ["A=1", "# comentario", "B=2", "C=3"]
        out = merge_env_lines(lines, {"B": "x", "C": None, "D": "4", "E": None})
        self.assertEqual(out, ["A=1", "# comentario", "B=x", "D=4"])

    def test_save_then_get_reads_env_before_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("NVIDIA_API_KEY='from-file'\nOTRA=1\n", encoding="utf-8")
            environ: dict[str, str] = {}
            creds = EnvCredentials(env_file, extra_files=(), environ=environ)
            self.assertEqual(creds.get("NVIDIA_API_KEY"), "from-file")
            self.assertIsNone(creds.get("NADA"))

            creds.save({"NVIDIA_API_KEY": "nuevo", "SCRIPT_PROVIDER": "nvidia"})
            self.assertEqual(creds.get("NVIDIA_API_KEY"), "nuevo")
            self.assertEqual(environ["SCRIPT_PROVIDER"], "nvidia")
            self.assertEqual(env_file.read_text(encoding="utf-8"), "NVIDIA_API_KEY=nuevo\nOTRA=1\nSCRIPT_PROVIDER=nvidia\n")
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)

            creds.save({"SCRIPT_PROVIDER": None})
            self.assertNotIn("SCRIPT_PROVIDER", environ)
            self.assertIsNone(creds.get("SCRIPT_PROVIDER"))


class SqliteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "nested" / "studio.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_video_repository_round_trip(self):
        repo = SqliteVideoRepository(self.db)
        vid = repo.add(NewVideo("Tema", "guion", "voz", {"font_size": 80}, [{"background": "a.mp4", "start": 0.0}]))
        record = repo.get(vid)
        self.assertEqual(record.status, "queued")
        self.assertEqual(record.style, {"font_size": 80})
        self.assertEqual(record.scenes, [{"background": "a.mp4", "start": 0.0}])

        repo.update(vid, status=VideoStatus.DONE, filename="/x.mp4", duration=1.5)
        repo.update(vid)  # sin campos no hace nada
        self.assertEqual(repo.get(vid).status, "done")
        self.assertEqual(repo.get(vid).filename, "/x.mp4")

        other = repo.add(NewVideo("Otro", "g", "v", {}, []))
        self.assertEqual([v.id for v in repo.list()], [other, vid])
        self.assertEqual(len(repo.list(limit=1)), 1)
        repo.remove(vid)
        self.assertIsNone(repo.get(vid))

    def test_event_log_offsets_keys_claims_and_commits(self):
        log = SqliteEventLog(self.db)
        a = log.publish("script.requested", "k1", {"topic": "uno"})
        b = log.publish("script.completed", "k1", {"script": "..."})
        c = log.publish("script.requested", "k2", {"topic": "dos"})
        self.assertEqual((a.offset, b.offset, c.offset), (1, 2, 3))
        self.assertEqual(log.last_offset(), 3)

        self.assertEqual([e.offset for e in log.read_after(0, ("script.requested",))], [1, 3])
        self.assertEqual([e.offset for e in log.read_after(2)], [3])
        self.assertEqual([e.topic for e in log.by_key("k1", ("script.completed", "script.failed"))], ["script.completed"])
        self.assertTrue(log.settled("k1", ("script.completed", "script.failed")))
        self.assertFalse(log.settled("k2", ("script.completed", "script.failed")))

        self.assertTrue(log.claim("k2"))
        self.assertFalse(log.claim("k2"))

        self.assertEqual(log.committed_offset("g"), 0)
        log.commit("g", 3)
        log.commit("g", 2)
        self.assertEqual(log.committed_offset("g"), 2)
        self.assertEqual(log.prune(), 0)

    def test_character_library_saves_by_name_and_keeps_the_reference(self):
        repo = SqliteCharacterRepository(self.db)
        ana = repo.upsert(Character("Ana", "pelo rojo"))
        pincel = repo.upsert(Character("Pincel", "robot naranja", "objeto"))
        repo.set_reference(ana.id, "ref-1.jpg")

        # «ana» sin tilde ni mayúscula es la misma: actualiza y conserva la referencia.
        again = repo.upsert(Character("ána", "pelo rojo y gafas", "persona"))
        self.assertEqual((again.id, again.name, again.traits, again.reference), (ana.id, "ána", "pelo rojo y gafas", "ref-1.jpg"))
        self.assertEqual(repo.find("ANA").id, ana.id)
        self.assertEqual(repo.get(pincel.id).kind, "objeto")
        self.assertEqual(len(repo.list()), 2)

        repo.remove(pincel.id)
        self.assertIsNone(repo.get(pincel.id))
        self.assertEqual([c.name for c in repo.list()], ["ána"])

    def test_wait_for_wakes_up_on_publish(self):
        log = SqliteEventLog(self.db)
        self.assertEqual(log.wait_for(0, timeout=0.05), [])
        timer = threading.Timer(0.05, lambda: log.publish("t", None, {}))
        timer.start()
        batch = log.wait_for(0, timeout=5.0)
        timer.join()
        self.assertEqual(len(batch), 1)


class ComposerCatalogTests(unittest.TestCase):
    def test_fallback_catalogs_need_no_network(self):
        composer = HttpScriptComposer()
        google = composer.catalog(provider_by_id("google"), api_key=None)
        self.assertEqual(google[0]["id"], "gemini-3.6-flash")
        anthropic = composer.catalog(provider_by_id("anthropic"), api_key=None)
        self.assertEqual([m["group"] for m in anthropic], ["Modelos"] * 3)
        deepseek = composer.catalog(provider_by_id("deepseek"), api_key=None)
        self.assertEqual(deepseek[0]["label"], "DeepSeek V4 Flash — rápido")


class MotionTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image, ImageDraw

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # Una imagen con una retícula: cualquier movimiento cambia los píxeles.
        image = Image.new("RGB", (432, 768), "white")
        draw = ImageDraw.Draw(image)
        for x in range(0, 432, 24):
            draw.line((x, 0, x, 768), fill="black")
        for y in range(0, 768, 24):
            draw.line((0, y, 432, y), fill="red")
        image.save(self.dir / "ia-x_1.jpg")
        (self.dir / "clip.mp4").write_bytes(b"no es un video")

    def tearDown(self):
        self._tmp.cleanup()

    def test_frames_move_within_a_shot_and_cut_between_shots(self):
        from app.infrastructure.motion import moving_image

        clip = moving_image(self.dir / "ia-x_1.jpg", 6.0, (108, 192), seed=1)
        self.assertEqual(clip.duration, 6.0)
        start, later, before_cut, after_cut = (clip.get_frame(t) for t in (0.0, 1.0, 2.95, 3.0))
        self.assertEqual(start.shape, (192, 108, 3))
        self.assertGreater(abs(start.astype(int) - later.astype(int)).mean(), 1)
        jump = abs(before_cut.astype(int) - after_cut.astype(int)).mean()
        drift = abs(later.astype(int) - clip.get_frame(1.05).astype(int)).mean()
        self.assertGreater(jump, 5 * drift)

    def test_build_track_moves_still_images_and_leaves_videos_to_the_engine(self):
        from app.infrastructure import render_worker

        built = []
        gen = SimpleNamespace(
            WIDTH=108, HEIGHT=192, IMAGE_EXTS={".jpg", ".png"},
            build_background=lambda path, topic, duration: built.append((path, duration)) or _solid(duration),
        )
        with mock.patch.object(render_worker, "emit"), \
                mock.patch.object(render_worker, "moving_image", side_effect=lambda p, d, size, seed: built.append(("mov", p.name, size)) or _solid(d)):
            track = render_worker.build_track(
                gen, self.dir, [{"background": "ia-x_1.jpg", "start": 0}, {"background": "clip.mp4", "start": 3}], "t", 5.0,
            )
        self.assertEqual(built, [("mov", "ia-x_1.jpg", (108, 192)), (self.dir / "clip.mp4", 2.0)])
        self.assertAlmostEqual(track.duration, 5.0)
        # La imagen va sin envoltorio y el video con él: la pista se pinta igual de seguido.
        for t in (0.5, 3.5):
            self.assertEqual(track.get_frame(t).shape, (192, 108, 3))


def _solid(duration: float):
    from moviepy import ColorClip

    return ColorClip((108, 192), color=(0, 0, 0)).with_duration(duration)


class ReferenceStoreTests(unittest.TestCase):
    def test_saves_reads_and_removes_only_reference_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileReferenceStore(Path(tmp) / "references")
            self.assertIsNone(store.read("ref-1.jpg"))
            store.save("ref-1.jpg", b"jpeg")
            self.assertEqual(store.read("ref-1.jpg"), b"jpeg")
            self.assertEqual(store.path("ref-1.jpg"), Path(tmp) / "references" / "ref-1.jpg")
            self.assertEqual([p.name for p in (Path(tmp) / "references").iterdir()], ["ref-1.jpg"])
            for bad in ("../studio.db", "ref-1.exe"):
                self.assertIsNone(store.path(bad))
                with self.assertRaises(ValueError):
                    store.save(bad, b"x")
            store.remove("ref-1.jpg")
            store.remove("ref-1.jpg")  # dos veces no falla
            self.assertIsNone(store.read("ref-1.jpg"))


class VisionTests(unittest.TestCase):
    @staticmethod
    def jpeg(width: int, height: int) -> GeneratedImage:
        from PIL import Image

        out = io.BytesIO()
        Image.new("RGB", (width, height), "orange").save(out, "JPEG")
        return GeneratedImage(out.getvalue(), ".jpg")

    def test_small_images_go_untouched_and_big_ones_shrink(self):
        small = self.jpeg(864, 1536)
        self.assertEqual(vision.fit(small), (small.data, "image/jpeg"))

        from PIL import Image

        data, media_type = vision.fit(self.jpeg(900, 1600))
        self.assertEqual(media_type, "image/jpeg")
        self.assertEqual(max(Image.open(io.BytesIO(data)).size), vision.MAX_SIDE)

    def test_openai_compatible_chat_sends_the_image_as_a_data_url(self):
        image = self.jpeg(64, 64)
        with mock.patch("requests.post") as post:
            post.return_value = fake_response(200, {"choices": [{"message": {"content": '{"ok": true}'}}]})
            answer = openai_compatible.chat(GOOGLE, "k", "gemini-3.6-flash", "sys", "Descripción", 30, image)
        self.assertEqual(answer, '{"ok": true}')
        text, picture = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertEqual(text, {"type": "text", "text": "Descripción"})
        self.assertEqual(picture["image_url"]["url"], "data:image/jpeg;base64," + b64(image.data))

        with mock.patch("requests.post") as post:
            post.return_value = fake_response(200, {"choices": [{"message": {"content": "guion"}}]})
            openai_compatible.chat(GOOGLE, "k", "m", "sys", "Tema", 30)
        self.assertEqual(post.call_args.kwargs["json"]["messages"][1]["content"], "Tema")

    def test_anthropic_gets_an_image_block_before_the_text(self):
        from app.infrastructure.llm import anthropic_client

        image = self.jpeg(64, 64)
        self.assertEqual(anthropic_client.user_content("Tema"), "Tema")
        picture, text = anthropic_client.user_content("Descripción", image)
        self.assertEqual(picture, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(image.data)}})
        self.assertEqual(text, {"type": "text", "text": "Descripción"})


class BackgroundStoreTests(unittest.TestCase):
    def test_save_is_atomic_and_has_sees_only_finished_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "bg"
            store = FileBackgroundStore(folder, Path(tmp) / "thumbs")
            self.assertFalse(store.has("mar_1.mp4"))
            self.assertEqual(store.save("/sub/mar_1.mp4", io.BytesIO(b"abc")), "mar_1.mp4")
            self.assertTrue(store.has("mar_1.mp4"))
            self.assertEqual((folder / "mar_1.mp4").read_bytes(), b"abc")
            # Un nombre con ruta se reduce al archivo: nada sale de la carpeta.
            self.assertEqual(store.path("../../mar_1.mp4"), folder / "mar_1.mp4")
            (folder / "notas.txt").write_text("x")
            self.assertIsNone(store.path("notas.txt"))

            # Borrar se lleva el archivo y su miniatura; con uno que no existe no pasa nada.
            thumb = ffmpeg.thumbnail_file(folder / "mar_1.mp4", Path(tmp) / "thumbs")
            thumb.parent.mkdir(parents=True, exist_ok=True)
            thumb.write_bytes(b"jpg")
            store.remove("mar_1.mp4")
            store.remove("mar_1.mp4")
            self.assertFalse(store.has("mar_1.mp4"))
            self.assertFalse(thumb.exists())

            class Cut:
                def read(self, size=-1):
                    raise EngineError("se cortó")

            with self.assertRaises(EngineError):
                store.save("mar_2.mp4", Cut())
            # Ni el archivo a medias ni su .part: la galería no ve nada roto.
            self.assertEqual([p.name for p in folder.iterdir() if p.name.startswith("mar_2")], [])


class PexelsTests(unittest.TestCase):
    VIDEO = {
        "id": 6799744, "duration": 12, "url": "https://www.pexels.com/video/6799744/",
        "image": "https://images.pexels.com/videos/6799744/free-video.jpg",
        "user": {"name": "Hanna Pad"},
        "video_files": [
            {"file_type": "video/mp4", "width": 1920, "height": 1080, "size": 9_000_000, "link": "https://cdn/h.mp4"},
            {"file_type": "video/mp4", "width": 720, "height": 1280, "size": 1_500_000, "link": "https://cdn/720.mp4"},
            {"file_type": "video/mp4", "width": 1080, "height": 1920, "size": 3_400_000, "link": "https://cdn/1080.mp4"},
            {"file_type": "video/mp4", "width": 2160, "height": 3840, "size": 30_000_000, "link": "https://cdn/4k.mp4"},
        ],
    }

    def test_parse_video_picks_the_vertical_1080_variant(self):
        clip = parse_video(self.VIDEO)
        self.assertEqual(
            (clip.id, clip.width, clip.height, clip.size_mb, clip.author, clip.link),
            (6799744, 1080, 1920, 3.4, "Hanna Pad", "https://cdn/1080.mp4"),
        )
        self.assertEqual(clip.preview, self.VIDEO["image"])
        self.assertEqual(clip.play, "https://cdn/720.mp4")  # la muestra es la más ligera
        landscape_only = {"id": 1, "video_files": [self.VIDEO["video_files"][0]]}
        self.assertIsNone(parse_video(landscape_only))

    def test_clip_stream_rejects_a_short_download(self):
        def response(body: bytes, length: int):
            return SimpleNamespace(
                headers={"Content-Length": str(length)},
                iter_content=lambda chunk_size: iter([body]),
                close=lambda: None,
            )

        with ClipStream(response(b"abc", 3), clip_id=1) as stream:
            self.assertEqual(b"".join(iter(lambda: stream.read(16), b"")), b"abc")
        with ClipStream(response(b"ab", 3), clip_id=1) as stream:
            with self.assertRaisesRegex(EngineError, "incompleto: 2 de 3 bytes"):
                while stream.read(16):
                    pass


def fake_response(status: int = 200, body: bytes | dict = b"", content_type: str = "application/json"):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode() if isinstance(body, dict) else body
    response.headers["Content-Type"] = content_type
    return response


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class ImagingTests(unittest.TestCase):
    def test_extension_comes_from_the_bytes_not_the_label(self):
        self.assertEqual(sniff_extension(b"\x89PNG....", "image/jpeg"), ".png")
        self.assertEqual(sniff_extension(b"\xff\xd8....", "image/png"), ".jpg")
        self.assertEqual(sniff_extension(b"RIFF\x00\x00\x00\x00WEBPVP8 "), ".webp")
        self.assertEqual(sniff_extension(b"????", "image/png"), ".png")
        self.assertEqual(sniff_extension(b"????"), ".jpg")

    def test_gemini_keeps_the_last_final_image(self):
        data = {"candidates": [{"content": {"parts": [
            {"text": "Aquí tienes"},
            {"inlineData": {"mimeType": "image/png", "data": b64(b"\x89PNGborrador")}, "thought": True},
            {"inlineData": {"mimeType": "image/png", "data": b64(b"\xff\xd8final")}},
        ]}, "finishReason": "STOP"}]}
        self.assertEqual(gemini.extract_image(data), GeneratedImage(b"\xff\xd8final", ".jpg"))

    def test_gemini_explains_blocks_and_empty_answers(self):
        with self.assertRaisesRegex(IllustratorError, r"rechazó la descripción \(SAFETY\)"):
            gemini.extract_image({"promptFeedback": {"blockReason": "SAFETY"}})
        with self.assertRaisesRegex(IllustratorError, r"ninguna imagen \(IMAGE_SAFETY\)"):
            gemini.extract_image({"candidates": [{"finishReason": "IMAGE_SAFETY", "content": {"parts": []}}]})

    def test_gemini_names_the_free_tier_and_bad_keys(self):
        free = fake_response(429, {"error": {"message": "Rate limit exceeded for model x (limit: 0 input tokens per minute on Free Tier)."}})
        with self.assertRaisesRegex(IllustratorError, "nivel gratuito"):
            gemini.raise_for_status(free, "x")
        with self.assertRaisesRegex(IllustratorError, "Límite de peticiones"):
            gemini.raise_for_status(fake_response(429, {"error": {"message": "slow down"}}), "x")
        with self.assertRaisesRegex(IllustratorError, "no es válida"):
            gemini.raise_for_status(fake_response(400, {"error": {"message": "API key not valid."}}), "x")
        with self.assertRaisesRegex(IllustratorError, "no sirve el modelo «x»"):
            gemini.raise_for_status(fake_response(404, {}), "x")
        gemini.raise_for_status(fake_response(200, {}), "x")

    def test_cloudflare_reads_the_envelope_and_raw_images(self):
        envelope = fake_response(200, {"result": {"image": b64(b"\xff\xd8ok")}, "success": True})
        self.assertEqual(cloudflare.extract_image(envelope), GeneratedImage(b"\xff\xd8ok", ".jpg"))
        raw = fake_response(200, b"\x89PNGraw", "image/png")
        self.assertEqual(cloudflare.extract_image(raw), GeneratedImage(b"\x89PNGraw", ".png"))
        with self.assertRaisesRegex(IllustratorError, "ninguna imagen"):
            cloudflare.extract_image(fake_response(200, {"result": {}, "success": True}))

    def test_cloudflare_errors_say_what_to_do(self):
        quota = fake_response(429, {"success": False, "errors": [
            {"code": 4006, "message": "you have used up your daily free allocation of 10,000 neurons"},
        ]})
        with self.assertRaisesRegex(IllustratorError, "cupo gratuito"):
            cloudflare.raise_for_status(quota, "m")
        auth = fake_response(401, {"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]})
        with self.assertRaisesRegex(IllustratorError, "rechazó el token"):
            cloudflare.raise_for_status(auth, "m")
        with self.assertRaisesRegex(IllustratorError, "no encuentra «m»"):
            cloudflare.raise_for_status(fake_response(404, b"not found", "text/plain"), "m")
        with self.assertRaisesRegex(IllustratorError, "Cloudflare devolvió 500: boom"):
            cloudflare.raise_for_status(fake_response(500, {"errors": [{"message": "boom"}]}), "m")
        flagged = fake_response(400, {"errors": [{"code": 3030, "message": "AiError: Your output has been flagged."}]})
        with self.assertRaisesRegex(IllustratorError, "filtro de contenido"):
            cloudflare.raise_for_status(flagged, "m")

    def test_cloudflare_sends_a_vertical_multipart_form(self):
        with mock.patch.object(cloudflare.requests, "post") as post:
            post.return_value = fake_response(200, {"result": {"image": b64(b"\xff\xd8ok")}})
            cloudflare.paint(" acc ", "tok", "@cf/m", "una taza", 30)
        url = post.call_args.args[0]
        self.assertEqual(url, "https://api.cloudflare.com/client/v4/accounts/acc/ai/run/@cf/m")
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})
        form = post.call_args.kwargs["files"]
        self.assertEqual((form["prompt"], form["width"], form["height"]), ((None, "una taza"), (None, "864"), (None, "1536")))
        self.assertNotIn("seed", form)

        with mock.patch.object(cloudflare.requests, "post") as post:
            post.return_value = fake_response(200, {"result": {"image": b64(b"\xff\xd8ok")}})
            cloudflare.paint("acc", "tok", "@cf/m", "una taza", 30, seed=42)
        self.assertEqual(post.call_args.kwargs["files"]["seed"], (None, "42"))

    def test_cloudflare_sends_up_to_four_shrunk_references(self):
        from PIL import Image

        def jpeg(width, height):
            out = io.BytesIO()
            Image.new("RGB", (width, height), "teal").save(out, "JPEG")
            return GeneratedImage(out.getvalue(), ".jpg")

        refs = [jpeg(864, 1536)] + [jpeg(300, 300)] * 4
        with mock.patch.object(cloudflare.requests, "post") as post:
            post.return_value = fake_response(200, {"result": {"image": b64(b"\xff\xd8ok")}})
            cloudflare.paint("acc", "tok", "@cf/m", "una taza", 30, seed=1, references=refs)
        form = post.call_args.kwargs["files"]
        self.assertEqual(sorted(k for k in form if k.startswith("input_image")), [f"input_image_{i}" for i in range(4)])
        name, data, mime = form["input_image_0"]
        self.assertEqual((name, mime), ("referencia_0.jpg", "image/jpeg"))
        self.assertEqual(Image.open(io.BytesIO(data)).size, (432, 768))
        self.assertEqual(Image.open(io.BytesIO(form["input_image_1"][1])).size, (300, 300))

    def test_gemini_asks_for_a_vertical_image_only(self):
        with mock.patch.object(gemini.requests, "post") as post:
            post.return_value = fake_response(200, {"candidates": [{"content": {"parts": [
                {"inlineData": {"mimeType": "image/jpeg", "data": b64(b"\xff\xd8ok")}},
            ]}}]})
            gemini.paint("key", "gemini-3.1-flash-lite-image", "una taza", 30)
        self.assertIn("gemini-3.1-flash-lite-image:generateContent", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "key")
        config = post.call_args.kwargs["json"]["generationConfig"]
        self.assertEqual(config["responseModalities"], ["IMAGE"])
        self.assertEqual(config["imageConfig"], {"aspectRatio": "9:16", "imageSize": "1K"})

    def test_illustrator_routes_by_provider(self):
        image = GeneratedImage(b"x", ".jpg")
        illustrator = HttpIllustrator(timeout=9)
        with mock.patch.object(gemini, "paint", return_value=image) as paint:
            illustrator.illustrate(image_provider_by_id("google"), "m", {"GEMINI_API_KEY": "k"}, "p")
        paint.assert_called_once_with("k", "m", "p", 9)
        with mock.patch.object(cloudflare, "paint", return_value=image) as paint:
            illustrator.illustrate(
                image_provider_by_id("cloudflare"), "m",
                {"CLOUDFLARE_ACCOUNT_ID": "a", "CLOUDFLARE_API_TOKEN": "t"}, "p", 7,
            )
        paint.assert_called_once_with("a", "t", "m", "p", 9, 7, ())


if __name__ == "__main__":
    unittest.main()
