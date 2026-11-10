"""Contrato HTTP con `web/infrastructure/http-gateway.ts`, sobre dobles."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.container import Container
from app.domain.video import RenderResult
from app.infrastructure.paths import Paths
from app.main import create_app
from tests.fakes import LONG_SCRIPT, DictCredentials, make_studio


class ApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.studio, self.fakes = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="n-key"))
        started = []
        container = Container(self.studio, Paths(tmp, tmp, tmp), workers=[lambda: started.append(1)])
        self.started = started
        self.client = TestClient(create_app(container))

    def tearDown(self):
        self._tmp.cleanup()

    def test_workers_start_with_the_server_not_on_import(self):
        self.assertEqual(self.started, [])
        with self.client:
            self.assertEqual(self.started, [1])

    def test_config_and_writer(self):
        config = self.client.get("/api/config").json()
        self.assertEqual(config["voices"][0], {"id": "es-MX-DaliaNeural", "label": "Dalia — México ♀"})
        self.assertEqual(config["default_style"]["font_size"], 92)
        self.assertEqual(config["writer"], "NVIDIA · llama-3.3-70b-instruct")
        self.assertEqual(config["generator"], "/fake/auto-video-generator")

        writer = self.client.get("/api/writer").json()
        self.assertEqual(writer["provider"], "nvidia")
        self.assertEqual(writer["providers"][0]["key_hint"], "…-key")

        saved = self.client.post("/api/writer", json={"provider": "google", "api_key": "g", "model": ""}).json()
        self.assertEqual(saved["provider"], "google")
        self.assertEqual(saved["label"], "Google · gemini-3.6-flash")
        bad = self.client.post("/api/writer", json={"provider": "openai"})
        self.assertEqual((bad.status_code, bad.json()["detail"]), (400, "Proveedor desconocido: openai"))

    def test_script_flow(self):
        accepted = self.client.post("/api/script", json={"topic": "gatos", "notes": ""})
        self.assertEqual(accepted.status_code, 202)
        job = accepted.json()["job"]
        self.assertEqual(self.client.get(f"/api/script/{job}").json(), {"status": "pending"})

        self.studio.scripts.handle_request(self.fakes.events.events[0])
        outcome = self.client.get(f"/api/script/{job}").json()
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(outcome["script"], LONG_SCRIPT)

        self.assertEqual(self.client.post("/api/script", json={"topic": " "}).status_code, 400)
        template = self.client.post("/api/script/template", json={"topic": "gatos"}).json()
        self.assertEqual(set(template), {"script", "seconds"})
        estimate = self.client.post("/api/estimate", json={"topic": "", "notes": LONG_SCRIPT}).json()
        self.assertEqual(estimate, {"seconds": 33.3, "words": 90, "in_range": True})

    def test_render_jobs_and_library(self):
        response = self.client.post("/api/render", json={
            "topic": "Tema", "script": LONG_SCRIPT, "scenes": [{"background": "a.mp4", "start": 2}],
        })
        self.assertEqual(response.json(), {"id": 1, "seconds": 33.3})
        (_, spec), = self.fakes.queue.enqueued
        self.assertEqual((spec.voice, spec.rate, spec.pitch), ("es-MX-DaliaNeural", "+8%", "+0Hz"))

        job = self.client.get("/api/jobs/1").json()
        self.assertEqual((job["id"], job["status"], job["progress"], job["message"]), (1, "queued", 0.0, "En cola"))
        self.assertEqual(self.client.get("/api/jobs").json()["active"][0]["id"], 1)
        self.assertEqual(self.client.get("/api/jobs/9").status_code, 404)
        self.assertEqual(self.client.post("/api/render", json={"topic": "t", "script": " "}).status_code, 400)

        self.assertEqual(self.client.get("/api/videos/1/file").status_code, 404)
        self.fakes.jobs.finished(1, RenderResult("/out/x.mp4", 33.0, 4.0, 10))
        items = self.client.get("/api/videos").json()["items"]
        self.assertEqual((items[0]["status"], items[0]["filename"], items[0]["scenes"]),
                         ("done", "/out/x.mp4", [{"background": "a.mp4", "start": 2.0}]))

        self.assertEqual(self.client.delete("/api/videos/1").json(), {"deleted": 1})
        self.assertEqual(self.fakes.files.removed, [Path("/out/x.mp4")])
        self.assertEqual(self.client.delete("/api/videos/1").status_code, 404)

    def test_backgrounds_and_preview(self):
        items = self.client.get("/api/backgrounds").json()["items"]
        self.assertEqual(items[0]["name"], "bosque_1.mp4")
        self.assertEqual(self.client.get("/api/thumb/nope.jpg").status_code, 404)
        self.assertEqual(self.client.get("/api/backgrounds/nope.mp4/file").status_code, 404)

        upload = self.client.post("/api/backgrounds/upload", files={"file": ("clip.mp4", b"abc", "video/mp4")})
        self.assertEqual(upload.json()["name"], "clip.mp4")
        bad = self.client.post("/api/backgrounds/upload", files={"file": ("notas.txt", b"x", "text/plain")})
        self.assertEqual((bad.status_code, bad.json()["detail"]), (400, "Formato no admitido: .txt"))

        found = self.client.get("/api/backgrounds/search", params={"q": "mar"}).json()["items"]
        self.assertEqual((found[0]["id"], found[0]["name"], found[0]["owned"]), (11, "mar_11.mp4", False))
        self.assertNotIn("link", found[0])
        self.assertEqual(self.client.get("/api/backgrounds/search", params={"q": " "}).status_code, 400)

        downloaded = self.client.post(
            "/api/backgrounds/download", json={"query": "mar", "ids": [11, 99]},
        ).json()
        self.assertEqual(downloaded["added"], ["mar_11.mp4"])
        self.assertEqual(downloaded["failed"], ["mar_99.mp4: Pexels ya no tiene el clip 99."])
        self.assertIn("mar_11.mp4", [b["name"] for b in downloaded["items"]])

        self.assertEqual(self.client.delete("/api/backgrounds/nope.mp4").status_code, 404)
        gone = self.client.delete("/api/backgrounds/mar_11.mp4").json()
        self.assertEqual(gone["deleted"], "mar_11.mp4")
        self.assertNotIn("mar_11.mp4", [b["name"] for b in gone["items"]])

        preview = self.client.post("/api/preview", json={"caption": "hola", "style": {}, "background": None})
        self.assertEqual(preview.headers["content-type"], "image/png")
        self.assertTrue(preview.content.startswith(b"\x89PNG"))

    def test_index_without_build_explains_how_to_run(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("./run.sh", response.text)


if __name__ == "__main__":
    unittest.main()
