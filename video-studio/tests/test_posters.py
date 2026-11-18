"""Las portadas en pequeño de la biblioteca: se pintan una vez y se guardan."""

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain.errors import NotFoundError
from app.domain.video import NewVideo
from app.infrastructure.paths import Paths
from app.infrastructure.posters import FilePosterStore
from tests.fakes import make_studio
from tests.test_infrastructure import FONTS


def add_video(fakes, fmt: str = "9:16") -> int:
    return fakes.videos.add(NewVideo(
        topic="Ayuno", script="palabra " * 20, voice="v",
        style={"production": {"format": fmt}}, scenes=[{"background": "bosque.jpg", "start": 0}],
        cover={"title": "El *ayuno*", "design": "impacto", "background": None},
    ))


class PosterUseCaseTests(unittest.TestCase):
    def test_paints_once_in_small_and_then_serves_the_saved_one(self):
        studio, fakes = make_studio()
        video_id = add_video(fakes)
        first = studio.cover.poster_of_video(video_id)
        again = studio.cover.poster_of_video(video_id)
        self.assertEqual(first, again)
        # Una sola vez, a tamaño completo y reducida a 360 de ancho.
        self.assertEqual(fakes.cover_painter.sizes, [(1080, 1920)])
        self.assertEqual(fakes.cover_painter.widths, [360])
        self.assertEqual(fakes.posters.files[video_id], first)

    def test_a_horizontal_video_gets_a_wider_poster(self):
        studio, fakes = make_studio()
        studio.cover.poster_of_video(add_video(fakes, "16:9"))
        self.assertEqual((fakes.cover_painter.sizes, fakes.cover_painter.widths), ([(1280, 720)], [480]))

    def test_a_missing_video_has_no_poster(self):
        studio, fakes = make_studio()
        with self.assertRaises(NotFoundError):
            studio.cover.poster_of_video(99)
        self.assertEqual(fakes.cover_painter.calls, [])

    def test_deleting_a_video_also_deletes_its_poster(self):
        studio, fakes = make_studio()
        video_id = add_video(fakes)
        studio.cover.poster_of_video(video_id)
        studio.library.delete(video_id)
        self.assertEqual(fakes.posters.removed, [video_id])
        self.assertNotIn(video_id, fakes.posters.files)


class PosterApiTests(unittest.TestCase):
    def test_the_poster_is_a_jpeg_the_browser_can_keep(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio, fakes = make_studio()
            client = TestClient(create_app(Container(studio, Paths(Path(tmp), Path(tmp), Path(tmp)), workers=[])))
            video_id = add_video(fakes)
            response = client.get(f"/api/videos/{video_id}/poster?v=2026-11-17")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/jpeg")
            self.assertIn("immutable", response.headers["cache-control"])
            self.assertEqual(client.get("/api/videos/99/poster").status_code, 404)


class FilePosterStoreTests(unittest.TestCase):
    def test_saves_reads_and_removes_by_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FilePosterStore(Path(tmp) / "posters")
            self.assertIsNone(store.read(3))
            store.save(3, b"jpeg")
            self.assertEqual(store.read(3), b"jpeg")
            self.assertEqual(sorted(p.name for p in (Path(tmp) / "posters").iterdir()), ["3.jpg"])
            store.remove(3)
            store.remove(3)  # dos veces no falla
            self.assertIsNone(store.read(3))


@unittest.skipUnless(FONTS, "Hace falta una fuente TTF del sistema")
class SmallCoverTests(unittest.TestCase):
    def test_the_real_painter_shrinks_keeping_the_shape(self):
        import numpy as np
        from PIL import Image

        from app.domain.cover import cover_words
        from app.infrastructure.cover import PillowCoverPainter

        gen = SimpleNamespace(
            resolve_font=lambda explicit: str(FONTS[0]),
            gradient_image=lambda hue, w, h, seed: np.full((h, w, 3), 90, dtype="uint8"),
        )
        data = PillowCoverPainter(gen).paint(cover_words("El *ayuno*"), "impacto", None, "tema", (540, 960), width=180)
        self.assertEqual(Image.open(io.BytesIO(data)).size, (180, 320))


if __name__ == "__main__":
    unittest.main()
