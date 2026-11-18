"""Contrato HTTP con `web/infrastructure/http-gateway.ts`, sobre dobles."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.container import Container
from app.domain.video import RenderResult
from app.infrastructure.paths import Paths
from app.api.factory import create_app
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

    def test_image_settings(self):
        settings = self.client.get("/api/images").json()
        self.assertEqual([p["id"] for p in settings["providers"]], ["cloudflare", "google"])
        self.assertIsNone(settings["label"])

        saved = self.client.post("/api/images", json={
            "provider": "cloudflare",
            "values": {"CLOUDFLARE_ACCOUNT_ID": "acc", "CLOUDFLARE_API_TOKEN": "tok-1234"},
        }).json()
        self.assertEqual(saved["label"], "Cloudflare · FLUX.2 klein 4B")
        self.assertEqual([f["hint"] for f in saved["providers"][0]["fields"]], ["acc", "…1234"])

        bad = self.client.post("/api/images", json={"provider": "cloudflare", "values": {"GEMINI_API_KEY": "x"}})
        self.assertEqual(bad.status_code, 400)

    def test_storyboard_is_queued_and_arrives_as_an_outcome(self):
        self.assertEqual(self.client.post("/api/storyboards", json={"topic": "t", "script": "  "}).status_code, 400)

        self.fakes.credentials.values["NVIDIA_API_KEY"] = "nv"
        self.fakes.composer.text = (
            '{"look": "óleo", "characters": [], "scenes": [{"from": 1, "description": "una taza al sol"}]}'
        )
        accepted = self.client.post("/api/storyboards", json={"topic": "Café", "script": "Hola mundo. Adiós."})
        self.assertEqual(accepted.status_code, 202)
        job = accepted.json()["job"]
        self.assertEqual(self.client.get(f"/api/outcomes/{job}").json(), {"status": "pending"})

        self.studio.storyboards.handle_request(self.fakes.events.events[-1])
        done = self.client.get(f"/api/outcomes/{job}").json()
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["guide"]["look"], "óleo")
        self.assertEqual(
            done["scenes"],
            [{"start": 0.0, "text": "Hola mundo. Adiós.", "description": "una taza al sol", "motion": ""}],
        )

    def test_illustrate_scenes(self):
        # Sin generador configurado, el encargo se rechaza con el motivo.
        refused = self.client.post("/api/illustrations", json={"topic": "Café", "description": "una taza"})
        self.assertEqual(refused.status_code, 400)
        self.assertIn("Generador de imágenes", refused.json()["detail"])

        self.fakes.credentials.values["GEMINI_API_KEY"] = "g-key"
        # Claude redacta y ve imágenes, así que revisa cada una.
        self.fakes.credentials.values["ANTHROPIC_API_KEY"] = "a-key"
        self.fakes.credentials.values["SCRIPT_PROVIDER"] = "anthropic"
        bad_cast = {"topic": "Café", "description": "una taza", "characters": [{"name": "Ana"}]}
        self.assertEqual(self.client.post("/api/illustrations", json=bad_cast).status_code, 400)
        accepted = self.client.post("/api/illustrations", json={
            "topic": "Café", "description": "Ana sirve una taza", "look": "óleo",
            "characters": [{"name": "Ana", "traits": "pelo rojo"}], "seed": 3,
        })
        self.assertEqual(accepted.status_code, 202)
        job = accepted.json()["job"]
        self.assertTrue(job.startswith("im-"))
        self.assertEqual(self.client.get(f"/api/outcomes/{job}").json(), {"status": "pending"})

        self.studio.illustrations.handle_request(self.fakes.events.events[-1])
        done = self.client.get(f"/api/outcomes/{job}").json()
        self.assertEqual(done["status"], "completed")
        self.assertTrue(done["name"].startswith("ia-cafe_"))
        self.assertEqual(done["provider"], "google")
        # El doble del compositor contesta un guion y no un veredicto: la
        # imagen llega igual, marcada como sin revisar.
        self.assertEqual(done["review"]["status"], "unchecked")

        unreviewed = self.client.post("/api/illustrations", json={"description": "una taza", "review": False})
        self.assertIsNone(self.fakes.events.events[-1].payload["review"])
        self.studio.illustrations.handle_request(self.fakes.events.events[-1])
        self.assertIsNone(self.client.get(f"/api/outcomes/{unreviewed.json()['job']}").json()["review"])

        # Corregir la imagen que acaba de llegar: sin descripción vale, sin decir qué está mal no.
        fix = {"topic": "Café", "source": done["name"], "correction": "Ana tiene tres brazos", "review": False}
        self.assertEqual(self.client.post("/api/illustrations", json={**fix, "correction": ""}).status_code, 400)
        self.assertEqual(self.client.post("/api/illustrations", json={**fix, "source": "nada_1.jpg"}).status_code, 404)
        corrected = self.client.post("/api/illustrations", json=fix)
        self.assertEqual(corrected.status_code, 202)
        self.studio.illustrations.handle_request(self.fakes.events.events[-1])
        fixed = self.client.get(f"/api/outcomes/{corrected.json()['job']}").json()
        self.assertEqual(fixed["status"], "completed")
        self.assertNotEqual(fixed["name"], done["name"])
        self.assertTrue(self.fakes.illustrator.calls[-1][3].startswith("Corrige la primera imagen de referencia"))

    def test_character_library(self):
        # Sin generador no se guarda: la referencia no se podría pintar.
        refused = self.client.post("/api/characters", json={"name": "Pincel", "traits": "robot"})
        self.assertEqual(refused.status_code, 400)

        self.fakes.credentials.values.update(CLOUDFLARE_ACCOUNT_ID="acc", CLOUDFLARE_API_TOKEN="tok")
        saved = self.client.post("/api/characters", json={
            "name": "Pincel", "traits": "robot de dibujo naranja", "kind": "objeto", "look": "acuarela",
        })
        self.assertEqual(saved.status_code, 202)
        body = saved.json()
        self.assertTrue(body["job"].startswith("rf-"))
        self.assertEqual(body["character"]["kind"], "objeto")
        self.assertIsNone(body["character"]["reference"])

        self.studio.characters.handle_request(self.fakes.events.events[-1])
        done = self.client.get(f"/api/outcomes/{body['job']}").json()
        self.assertEqual((done["status"], done["reference"]), ("completed", "ref-1.jpg"))
        (listed,) = self.client.get("/api/characters").json()
        self.assertEqual((listed["name"], listed["reference"]), ("Pincel", "ref-1.jpg"))

        again = self.client.post("/api/characters", json={"name": "pincel", "traits": "robot de dibujo naranja", "kind": "objeto"})
        self.assertIsNone(again.json()["job"])
        repaint = self.client.post(f"/api/characters/{listed['id']}/reference", json={"look": "óleo"})
        self.assertEqual(repaint.status_code, 202)
        self.assertEqual(self.client.get("/api/references/ref-9.jpg").status_code, 404)
        self.assertEqual(self.client.get("/api/references/..%2Fstudio.db").status_code, 404)

        self.assertEqual(self.client.delete(f"/api/characters/{listed['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/characters").json(), [])
        self.assertEqual(self.client.delete(f"/api/characters/{listed['id']}").status_code, 404)

    def test_storyboard_takes_the_cast_already_in_the_video(self):
        cast = [{"name": "Ana", "traits": "pelo rojo", "kind": "persona", "saved": 3}]
        accepted = self.client.post("/api/storyboards", json={"topic": "t", "script": "Hola mundo. Adiós.", "characters": cast})
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(self.fakes.events.events[-1].payload["characters"], cast)
        bad = self.client.post("/api/storyboards", json={"script": "Hola.", "characters": [{"name": "Ana", "kind": "x", "traits": "t"}]})
        self.assertEqual(bad.status_code, 400)

    def test_writer_settings_say_whether_it_can_review_images(self):
        self.assertFalse(self.client.get("/api/writer").json()["sees_images"])
        self.fakes.credentials.values["DEEPSEEK_API_KEY"] = "d"
        self.assertFalse(self.client.get("/api/writer").json()["sees_images"])
        self.fakes.credentials.values["ANTHROPIC_API_KEY"] = "a"
        self.fakes.credentials.values["SCRIPT_PROVIDER"] = "anthropic"
        self.assertTrue(self.client.get("/api/writer").json()["sees_images"])


    def test_cover_paints_suggests_and_downloads(self):
        painted = self.client.post("/api/cover", json={
            "title": "El *truco*", "design": "franja", "background": "bosque_1.mp4", "topic": "t",
        })
        self.assertEqual(painted.status_code, 200)
        self.assertEqual(painted.headers["content-type"], "image/jpeg")
        self.assertEqual(painted.content, b"\xff\xd8JPEG EL TRUCO")
        bad = self.client.post("/api/cover", json={"title": " ", "design": "impacto"})
        self.assertEqual((bad.status_code, bad.json()["detail"]), (400, "Escribe el título de la portada."))

        accepted = self.client.post("/api/cover/titles", json={"topic": "ayuno", "script": ""})
        self.assertEqual(accepted.status_code, 202)
        job = accepted.json()["job"]
        self.assertEqual(self.client.get(f"/api/outcomes/{job}").json(), {"status": "pending"})

        self.client.post("/api/render", json={
            "topic": "Ayuno real", "script": LONG_SCRIPT,
            "cover": {"title": "El *ayuno*", "design": "titular", "background": None},
        })
        item = self.client.get("/api/videos").json()["items"][0]
        self.assertEqual(item["cover"], {"title": "El *ayuno*", "design": "titular", "background": None})
        download = self.client.get(f"/api/videos/{item['id']}/cover")
        self.assertEqual(download.content, b"\xff\xd8JPEG EL AYUNO")
        self.assertEqual(
            download.headers["content-disposition"], "attachment; filename*=UTF-8''portada-ayuno-real.jpg",
        )
        self.assertEqual(self.client.get("/api/videos/99/cover").status_code, 404)

    def test_description_is_requested_and_saved_with_the_video(self):
        accepted = self.client.post("/api/description", json={"topic": "t", "script": "Un guion.", "title": "El *t*"})
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(self.fakes.events.events[-1].payload["title"], "El t")
        empty = self.client.post("/api/description", json={"topic": "t", "script": " "})
        self.assertEqual(empty.status_code, 400)

        self.client.post("/api/render", json={"topic": "t", "script": LONG_SCRIPT, "description": " Texto \n#tag "})
        self.assertEqual(self.client.get("/api/videos").json()["items"][0]["description"], "Texto\n#tag")


if __name__ == "__main__":
    unittest.main()
