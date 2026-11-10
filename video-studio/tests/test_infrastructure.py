import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.domain.errors import EngineError
from app.domain.video import NewVideo, VideoStatus
from app.domain.writer import provider_by_id
from app.infrastructure import ffmpeg
from app.infrastructure.backgrounds import FileBackgroundStore
from app.infrastructure.env_credentials import EnvCredentials, merge_env_lines
from app.infrastructure.llm.composer import HttpScriptComposer
from app.infrastructure.pexels import ClipStream, parse_video
from app.infrastructure.sqlite import Database, SqliteEventLog, SqliteVideoRepository


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


if __name__ == "__main__":
    unittest.main()
