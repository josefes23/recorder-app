"""Escenas animadas: dominio, caso de uso, adaptador de Gemini Omni y ruta."""

import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain import animation
from app.domain.animation import (
    MAX_SECONDS,
    GeneratedClip,
    animation_name,
    animation_prompt,
    clip_seconds,
    validate_motion,
    validate_seconds,
)
from app.domain.background import Background
from app.domain.errors import AnimatorError, NotFoundError, ValidationError
from app.domain.events import ANIMATION_COMPLETED, ANIMATION_FAILED, ANIMATION_REQUESTED
from app.domain.illustration import Character, GeneratedImage, VisualGuide
from app.infrastructure.animation import gemini_omni
from app.infrastructure.paths import Paths
from tests.fakes import DictCredentials, make_studio

IMAGE = "ia-cafe_123.jpg"


def jpeg() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (864, 1536), (200, 120, 40)).save(out, "JPEG")
    return out.getvalue()


def fake_response(status: int = 200, body: bytes | dict = b"", content_type: str = "application/json"):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode() if isinstance(body, dict) else body
    response.headers["Content-Type"] = content_type
    return response


class AnimationDomainTests(unittest.TestCase):
    def test_the_clip_covers_its_span_rounding_up_within_the_model_limits(self):
        self.assertEqual(clip_seconds(6.0), 6)
        self.assertEqual(clip_seconds(6.0000001), 6)  # ruido de flotantes, no un segundo más
        self.assertEqual(clip_seconds(6.2), 7)
        self.assertEqual(clip_seconds(1.5), 3)
        self.assertEqual(clip_seconds(40), MAX_SECONDS)

    def test_seconds_must_be_whole_and_within_limits(self):
        self.assertEqual(validate_seconds(8), 8)
        self.assertEqual(validate_seconds(8.0), 8)
        for bad in (2, 16, 4.5, True, "8", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                validate_seconds(bad)

    def test_the_clip_sits_next_to_its_image_and_does_not_overwrite_older_ones(self):
        self.assertEqual(animation_name(IMAGE, "an-a1b2c3d4e5"), "ia-cafe_123-mov-a1b2c3.mp4")
        self.assertNotEqual(animation_name(IMAGE, "an-000000aaaa"), animation_name(IMAGE, "an-111111aaaa"))

    def test_prompt_keeps_the_first_frame_and_asks_for_silence(self):
        ana = Character("Ana", "pelo rojo, delantal verde")
        prompt = animation_prompt("Ana sirve un café", VisualGuide("acuarela cálida", (ana,)))
        self.assertTrue(prompt.startswith(animation.FIRST_FRAME))
        self.assertIn("Qué pasa: Ana sirve un café.", prompt)
        self.assertIn("Ana: pelo rojo, delantal verde.", prompt)
        self.assertIn("Estilo: acuarela cálida.", prompt)
        self.assertIn("Sin diálogos", prompt)

    def test_prompt_without_description_still_has_style_and_motion(self):
        prompt = animation_prompt("")
        self.assertNotIn("Qué pasa", prompt)
        self.assertIn("Estilo:", prompt)
        self.assertIn(f"{animation.MOTION} {animation.ONE_SHOT}", prompt)

    def test_the_scene_motion_replaces_the_generic_one_and_keeps_a_single_shot(self):
        prompt = animation_prompt("Ana sirve un café", motion="  el vapor sube;\n la cámara se acerca despacio ")
        self.assertIn("Movimiento: el vapor sube; la cámara se acerca despacio. Un solo plano, sin cortes.", prompt)
        self.assertNotIn(animation.MOTION, prompt)
        # El orden: qué pasa, estilo, movimiento y, al final, el silencio.
        lines = prompt.splitlines()
        self.assertTrue(lines[-2].startswith("Movimiento:"))
        self.assertEqual(lines[-1], animation.QUIET)

    def test_motion_is_one_line_and_has_a_limit(self):
        self.assertEqual(validate_motion("  la cámara\n se aleja "), "la cámara se aleja")
        self.assertEqual(validate_motion(None), "")
        self.assertEqual(len(validate_motion("x" * animation.MOTION_LIMIT)), animation.MOTION_LIMIT)
        with self.assertRaisesRegex(ValidationError, "demasiado largo"):
            validate_motion("x" * (animation.MOTION_LIMIT + 1))


class AnimationUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.studio, self.fakes = make_studio(credentials=DictCredentials(GEMINI_API_KEY="g-key"))
        self.fakes.backgrounds.items.append(Background.describe(IMAGE, 0.0, 1000, None))
        self.fakes.backgrounds.data[IMAGE] = b"\xff\xd8imagen"

    def request(self, **overrides):
        args = {"topic": " Café ", "source": IMAGE, "seconds": 6, "description": "Ana sirve un café",
                "look": "acuarela", "characters": [{"name": "Ana", "traits": "pelo rojo"}], "seed": 7}
        args.update(overrides)
        return self.studio.animations.request(**args)

    def test_request_publishes_the_job_with_the_video_guide(self):
        event = self.request()
        self.assertEqual(event.topic, ANIMATION_REQUESTED)
        self.assertTrue(event.key.startswith("an-"))
        self.assertEqual(event.payload["source"], IMAGE)
        self.assertEqual(event.payload["seconds"], 6)
        self.assertEqual(event.payload["topic"], "Café")
        self.assertEqual(event.payload["look"], "acuarela")
        self.assertEqual(event.payload["model"], "gemini-omni-1.2-flash")
        self.assertEqual(event.payload["motion"], "")

    def test_the_scene_motion_travels_with_the_job_and_reaches_the_prompt(self):
        event = self.request(motion=" la cámara se acerca\n a Ana ")
        self.assertEqual(event.payload["motion"], "la cámara se acerca a Ana")
        self.studio.animations.handle_request(event)
        prompt = self.fakes.animator.calls[0][4]
        self.assertIn("Movimiento: la cámara se acerca a Ana. Un solo plano, sin cortes.", prompt)

        with self.assertRaisesRegex(ValidationError, "demasiado largo"):
            self.request(motion="x" * (animation.MOTION_LIMIT + 1))

    def test_only_images_from_the_gallery_are_animated(self):
        with self.assertRaisesRegex(ValidationError, "Solo se animan imágenes"):
            self.request(source="bosque_1.mp4")
        with self.assertRaises(NotFoundError):
            self.request(source="no-esta.jpg")
        with self.assertRaisesRegex(ValidationError, "Elige la imagen"):
            self.request(source=" ")
        with self.assertRaisesRegex(ValidationError, "entre 3 y 15"):
            self.request(seconds=20)

    def test_without_the_google_key_it_says_what_is_missing(self):
        self.fakes.credentials.values.pop("GEMINI_API_KEY")
        with self.assertRaisesRegex(ValidationError, "GEMINI_API_KEY"):
            self.request()
        self.assertEqual(self.fakes.events.events, [])

    def test_the_clip_lands_in_the_gallery_and_the_job_completes(self):
        event = self.request()
        self.studio.animations.handle_request(event)

        provider, model, credentials, image, prompt, seconds = self.fakes.animator.calls[0]
        self.assertEqual((provider, model, seconds), ("google", "gemini-omni-1.2-flash", 6))
        self.assertEqual(credentials, {"GEMINI_API_KEY": "g-key"})
        self.assertEqual(image, b"\xff\xd8imagen")
        self.assertIn("Ana: pelo rojo.", prompt)

        name = animation_name(IMAGE, event.key)
        self.assertIn(name, self.fakes.backgrounds.saved)
        done = self.fakes.events.by_key(event.key, (ANIMATION_COMPLETED,))[0]
        self.assertEqual(done.payload["name"], name)
        self.assertEqual(done.payload["source"], IMAGE)
        self.assertEqual(self.studio.outcome(event.key)["status"], "completed")

    def test_a_failure_closes_the_job_with_its_reason(self):
        self.fakes.animator.error = AnimatorError("Gemini Omni no tiene nivel gratuito")
        event = self.request()
        self.studio.animations.handle_request(event)
        failed = self.fakes.events.by_key(event.key, (ANIMATION_FAILED,))[0]
        self.assertIn("nivel gratuito", failed.payload["detail"])
        self.assertEqual(self.fakes.backgrounds.saved, [])

    def test_an_image_deleted_before_its_turn_fails_cleanly(self):
        event = self.request()
        self.fakes.backgrounds.remove(IMAGE)
        self.studio.animations.handle_request(event)
        failed = self.fakes.events.by_key(event.key, (ANIMATION_FAILED,))[0]
        self.assertIn("ya no está en la galería", failed.payload["detail"])
        self.assertEqual(self.fakes.animator.calls, [])

    def test_a_job_delivered_twice_is_animated_once(self):
        event = self.request()
        self.studio.animations.handle_request(event)
        self.studio.animations.handle_request(event)
        self.assertEqual(len(self.fakes.animator.calls), 1)

    def test_settings_say_whether_it_is_ready_and_allow_another_model(self):
        settings = self.studio.animations.settings()
        self.assertTrue(settings["ready"])
        self.assertEqual(settings["usd_per_second"], 0.07)
        self.fakes.credentials.values["GEMINI_VIDEO_MODEL"] = "gemini-omni-1.1-flash"
        self.assertEqual(self.studio.animations.settings()["model"], "gemini-omni-1.1-flash")
        self.fakes.credentials.values.pop("GEMINI_API_KEY")
        self.assertFalse(self.studio.animations.settings()["ready"])


class GeminiOmniTests(unittest.TestCase):
    def test_body_asks_for_a_vertical_clip_of_the_span_from_the_image(self):
        body = gemini_omni.request_body("gemini-omni-1.2-flash", GeneratedImage(jpeg(), ".jpg"), "anima", 6, "720p")
        self.assertEqual(body["model"], "gemini-omni-1.2-flash")
        image, text = body["input"]
        self.assertEqual((image["type"], image["mime_type"]), ("image", "image/jpeg"))
        self.assertTrue(base64.b64decode(image["data"]).startswith(b"\xff\xd8"))
        self.assertEqual(text, {"type": "text", "text": "anima"})
        self.assertEqual(
            body["response_format"],
            {"type": "video", "aspect_ratio": "9:16", "resolution": "720p", "duration": "6s", "delivery": "uri"},
        )
        self.assertEqual(body["generation_config"], {"video_config": {"task": "image_to_video"}})

    def test_the_video_is_found_inline_or_by_uri(self):
        steps = {"steps": [
            {"type": "user_input", "content": [{"type": "text", "text": "..."}]},
            {"type": "model_output", "content": [
                {"type": "video", "mime_type": "video/mp4", "uri": "https://x/v1beta/files/abc123:download?alt=media"},
            ]},
        ], "status": "completed"}
        self.assertEqual(gemini_omni.extract_video(steps), (None, "https://x/v1beta/files/abc123:download?alt=media"))
        inline = {"output_video": {"data": base64.b64encode(b"mp4").decode()}}
        self.assertEqual(gemini_omni.extract_video(inline), (b"mp4", None))
        self.assertEqual(gemini_omni.file_id(steps["steps"][1]["content"][0]["uri"]), "abc123")

    def test_no_video_explains_the_likely_filter(self):
        with self.assertRaisesRegex(AnimatorError, r"ningún video \(estado: failed\)"):
            gemini_omni.extract_video({"steps": [], "status": "failed"})

    def test_errors_say_what_to_do(self):
        with self.assertRaisesRegex(AnimatorError, "no tiene nivel gratuito"):
            gemini_omni.raise_for_status(fake_response(429, {"error": {"message": "limit: 0, Free Tier"}}), "m")
        with self.assertRaisesRegex(AnimatorError, "no es válida"):
            gemini_omni.raise_for_status(fake_response(400, {"error": {"message": "API key not valid."}}), "m")
        with self.assertRaisesRegex(AnimatorError, "GEMINI_VIDEO_MODEL"):
            gemini_omni.raise_for_status(fake_response(404, {}), "m")
        with self.assertRaisesRegex(AnimatorError, "filtros"):
            gemini_omni.raise_for_status(fake_response(400, {"error": {"message": "blocked by safety"}}), "m")
        gemini_omni.raise_for_status(fake_response(200, {}), "m")

    def test_waits_for_the_file_and_downloads_it(self):
        created = fake_response(200, {"steps": [{"type": "model_output", "content": [
            {"type": "video", "uri": "https://generativelanguage.googleapis.com/v1beta/files/f1:download?alt=media"},
        ]}], "status": "completed"})
        states = [fake_response(200, {"state": "PROCESSING"}), fake_response(200, {"state": "ACTIVE"})]
        video = fake_response(200, b"\x00\x00\x00\x18ftypmp42", "video/mp4")
        naps: list[float] = []
        with mock.patch.object(gemini_omni.requests, "post", return_value=created) as post, \
                mock.patch.object(gemini_omni.requests, "get", side_effect=[*states, video]) as get:
            clip = gemini_omni.animate("key", "m", GeneratedImage(jpeg(), ".jpg"), "anima", 5, "720p", 60, naps.append)
        self.assertEqual(clip, GeneratedClip(b"\x00\x00\x00\x18ftypmp42"))
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "key")
        self.assertTrue(get.call_args_list[0].args[0].endswith("/files/f1"))
        self.assertTrue(get.call_args_list[-1].args[0].endswith("/files/f1:download?alt=media"))
        self.assertEqual(naps, [gemini_omni.POLL_SECONDS])

    def test_a_failed_file_is_an_error(self):
        with mock.patch.object(gemini_omni.requests, "get", return_value=fake_response(200, {"state": "FAILED"})):
            with self.assertRaisesRegex(AnimatorError, "no pudo terminar"):
                gemini_omni.download("https://x/v1beta/files/f1:download?alt=media", {}, lambda _: None)


class AnimationApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.studio, self.fakes = make_studio(credentials=DictCredentials(GEMINI_API_KEY="g-key"))
        self.fakes.backgrounds.items.append(Background.describe(IMAGE, 0.0, 1000, None))
        self.client = TestClient(create_app(Container(self.studio, Paths(tmp, tmp, tmp), workers=[])))

    def tearDown(self):
        self._tmp.cleanup()

    def test_settings_and_request(self):
        self.assertTrue(self.client.get("/api/animations").json()["ready"])
        response = self.client.post("/api/animations", json={"topic": "Café", "source": IMAGE, "seconds": 6})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["job"].startswith("an-"))

        moving = self.client.post(
            "/api/animations", json={"source": IMAGE, "seconds": 6, "motion": "la cámara se aleja"}
        )
        self.assertEqual(moving.status_code, 202)
        self.assertEqual(self.fakes.events.events[-1].payload["motion"], "la cámara se aleja")

    def test_a_clip_cannot_be_animated(self):
        response = self.client.post("/api/animations", json={"source": "bosque_1.mp4", "seconds": 6})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Solo se animan imágenes", response.json()["detail"])
