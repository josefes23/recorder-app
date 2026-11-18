"""Tomas de voz: escuchar antes de renderizar y recuperar los tiempos reales después."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain.errors import EngineError, NotFoundError, ValidationError
from app.domain.voice_take import TakeRequest, clean_words, is_take_key, take_key, take_request
from app.infrastructure.paths import Paths
from app.infrastructure.takes import MAX_AUDIO, FileTakeStore
from tests.fakes import make_studio

SCRIPT = "**Hola** mundo, esto es una prueba. " * 3


class TakeKeyTests(unittest.TestCase):
    def test_the_same_input_is_the_same_take_and_any_change_is_another(self):
        base = take_request(SCRIPT, "es-MX-DaliaNeural", "+8%", "+0Hz", {})
        self.assertEqual(take_key(base), take_key(take_request(SCRIPT, "es-MX-DaliaNeural", "+8%", "+0Hz", None)))
        self.assertTrue(is_take_key(take_key(base)))
        # La limpieza del guion no cambia la toma: es lo que se sintetiza lo que cuenta.
        self.assertEqual(take_key(base), take_key(take_request(f"  {SCRIPT}\n", "es-MX-DaliaNeural", "+8%", "+0Hz", {})))
        for changed in (
            take_request(SCRIPT + " más", "es-MX-DaliaNeural", "+8%", "+0Hz", {}),
            take_request(SCRIPT, "es-MX-JorgeNeural", "+8%", "+0Hz", {}),
            take_request(SCRIPT, "es-MX-DaliaNeural", "+0%", "+0Hz", {}),
        ):
            self.assertNotEqual(take_key(base), take_key(changed))

    def test_an_empty_script_has_no_take_and_defaults_fill_the_voice(self):
        with self.assertRaises(ValidationError):
            take_request(" ** ", "", "", "", {})
        self.assertEqual(take_request("Hola", "", "", "", {}), TakeRequest("Hola", "es-MX-DaliaNeural", "+8%", "+0Hz", {}))

    def test_stored_marks_are_checked(self):
        self.assertEqual(clean_words([{"text": "a", "start": "1", "end": 1.5}, {"text": "b"}, "x"]),
                         [{"text": "a", "start": 1.0, "end": 1.5}])
        self.assertEqual(clean_words(None), [])


class TakeUseCaseTests(unittest.TestCase):
    def test_a_take_is_synthesized_once_and_then_reused(self):
        studio, fakes = make_studio()
        first = studio.takes.take(SCRIPT, "v", "+8%", "+0Hz")
        again = studio.takes.take(SCRIPT, "v", "+8%", "+0Hz")
        self.assertEqual(first, again)
        self.assertEqual(len(fakes.synthesizer.requests), 1)
        self.assertEqual(first.words[0], {"text": "Hola", "start": 0.0, "end": 0.35})
        self.assertEqual(studio.takes.get(first.key), first)
        self.assertEqual(studio.takes.audio_of(first.key), Path("/takes") / f"{first.key}.mp3")

    def test_unknown_or_malformed_keys_are_not_found(self):
        studio, _ = make_studio()
        for key in ("0123456789abcdef", "../../etc/passwd"):
            with self.assertRaises(NotFoundError):
                studio.takes.get(key)
            with self.assertRaises(NotFoundError):
                studio.takes.audio_of(key)

    def test_the_render_remembers_the_take_of_its_script_and_voice(self):
        studio, fakes = make_studio()
        take = studio.takes.take(SCRIPT, "v", "+8%", "+0Hz")
        video_id, _ = studio.render.start("t", SCRIPT, "v", "+8%", "+0Hz", {}, [])
        spec = fakes.queue.enqueued[-1][1]
        self.assertEqual(spec.take, take.key)
        self.assertEqual(fakes.videos.get(video_id).style["production"]["take"], take.key)

    def test_the_take_key_cannot_come_from_the_interface(self):
        studio, fakes = make_studio()
        studio.render.start("t", SCRIPT, "v", "+8%", "+0Hz", {}, [], production={"take": "0123456789abcdef"})
        self.assertNotEqual(fakes.queue.enqueued[-1][1].take, "0123456789abcdef")


class TakeApiTests(unittest.TestCase):
    def test_make_and_read_a_take(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio, _ = make_studio()
            client = TestClient(create_app(Container(studio, Paths(Path(tmp), Path(tmp), Path(tmp)), workers=[])))
            made = client.post("/api/takes", json={"script": SCRIPT})
            self.assertEqual(made.status_code, 200)
            body = made.json()
            self.assertEqual(set(body), {"key", "duration", "words", "audio"})
            self.assertEqual(client.get(f"/api/takes/{body['key']}").json(), body)
            self.assertEqual(client.post("/api/takes", json={"script": "  "}).status_code, 400)
            self.assertEqual(client.get("/api/takes/0123456789abcdef").status_code, 404)


class FileTakeStoreTests(unittest.TestCase):
    def test_saves_reads_and_keeps_the_marks_when_old_audio_is_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileTakeStore(Path(tmp))
            keys = [f"{i:016x}" for i in range(MAX_AUDIO + 2)]
            for i, key in enumerate(keys):
                store.save(key, b"ID3", [{"text": "hola", "start": 0, "end": 0.4}], 1.5)
                # Mtimes distintos y en orden, aunque el disco redondee.
                path = Path(tmp) / f"{key}.mp3"
                stamp = 1_700_000_000 + i
                import os
                os.utime(path, (stamp, stamp))
            store.save(keys[-1], b"ID3", [], 1.5)  # vuelve a podar
            oldest = store.get(keys[0])
            self.assertIsNotNone(oldest)
            self.assertFalse(oldest.audio)
            self.assertIsNone(store.audio(keys[0]))
            self.assertTrue(store.get(keys[-2]).audio)
            self.assertEqual(json.loads((Path(tmp) / f"{keys[0]}.json").read_text())["duration"], 1.5)
            self.assertIsNone(store.get("../x"))


class QueueTests(unittest.TestCase):
    def test_the_worker_looks_for_takes_where_the_server_keeps_them(self):
        from app.domain.video import RenderSpec
        from app.infrastructure.render_queue import SubprocessRenderQueue

        listener = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            queue = SubprocessRenderQueue(Path(tmp) / "jobs", Path(tmp) / "out", Path(tmp), listener, takes_dir=Path(tmp) / "takes")
            queue.enqueue(1, RenderSpec(topic="t", script="Hola", voice="v", rate="+0%", pitch="+0Hz", take="0123456789abcdef"))
            job = json.loads((Path(tmp) / "jobs" / "1.json").read_text(encoding="utf-8"))
            self.assertEqual(job["takes_dir"], str(Path(tmp) / "takes"))
            spec = RenderSpec.from_dict(job)
            self.assertEqual((spec.take, spec.takes_dir), ("0123456789abcdef", str(Path(tmp) / "takes")))


class SynthesizerTests(unittest.TestCase):
    def test_engine_failures_reach_the_user_as_engine_errors(self):
        from app.infrastructure.voice import EngineVoiceSynthesizer

        with tempfile.TemporaryDirectory() as tmp:
            gen = mock.Mock()
            gen.synthesize_voice.side_effect = SystemExit("ERROR: edge-tts devolvió un audio vacío.")
            synth = EngineVoiceSynthesizer(gen, Path(tmp))
            with self.assertRaises(EngineError) as raised:
                synth.synthesize(take_request("Hola", "", "", "", {}))
            self.assertIn("audio vacío", str(raised.exception))
            gen.synthesize_voice.side_effect = OSError("sin red")
            with self.assertRaises(EngineError):
                synth.synthesize(take_request("Hola", "", "", "", {}))
            self.assertEqual(list(Path(tmp).iterdir()), [])  # no deja audios a medias


if __name__ == "__main__":
    unittest.main()
