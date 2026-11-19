"""ElevenLabs conviviendo con edge-tts: elegir voz por voz, sin cambiar lo que ya funcionaba."""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.container import Container
from app.domain.errors import EngineError
from app.domain.voice import SAMPLE_TEXT, eleven_speed, eleven_voice, is_eleven
from app.infrastructure.elevenlabs import ElevenLabsClient, VoiceRouter, words_from_alignment
from app.infrastructure.paths import Paths
from tests.fakes import DictCredentials, make_studio

ALIGNMENT = {
    "characters": list("Hola mundo"),
    "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
}


class VoiceIdTests(unittest.TestCase):
    def test_only_prefixed_ids_are_elevenlabs(self):
        self.assertTrue(is_eleven("eleven:abc"))
        for other in ("es-MX-DaliaNeural", "eleven:", "", None):
            self.assertFalse(is_eleven(other))

    def test_edge_rate_becomes_a_speed_within_what_elevenlabs_accepts(self):
        self.assertEqual(eleven_speed("+8%"), 1.08)
        self.assertEqual(eleven_speed("-10%"), 0.9)
        self.assertEqual(eleven_speed("+90%"), 1.2)
        self.assertEqual(eleven_speed("-90%"), 0.7)
        self.assertEqual(eleven_speed("raro"), 1.0)


class AlignmentTests(unittest.TestCase):
    def test_characters_are_grouped_into_words(self):
        words = words_from_alignment(ALIGNMENT)
        self.assertEqual([w["text"] for w in words], ["Hola", "mundo"])
        self.assertEqual((words[0]["start"], words[0]["end"]), (0.0, 0.4))
        self.assertEqual((words[1]["start"], words[1]["end"]), (0.5, 1.0))

    def test_no_alignment_is_no_words(self):
        self.assertEqual(words_from_alignment({}), [])


class VoiceLabelTests(unittest.TestCase):
    def test_the_label_says_accent_and_gender_when_the_account_does(self):
        full = eleven_voice("a", "Rachel", "american", "female", "https://x/r.mp3")
        self.assertEqual(full.label, "Rachel — american ♀ — ElevenLabs")
        self.assertEqual(full.preview, "https://x/r.mp3")
        self.assertEqual(eleven_voice("b", "Adam").label, "Adam — ElevenLabs")
        self.assertEqual(eleven_voice("c", "Sam", gender="male").label, "Sam — ♂ — ElevenLabs")

    def test_the_account_list_carries_labels_and_samples(self):
        payload = {"voices": [
            {"voice_id": "a", "name": "Rachel", "labels": {"accent": "american", "gender": "female"}, "preview_url": "https://x/r.mp3"},
            {"voice_id": "b", "name": "Sin datos", "labels": None},
            {"name": "sin id"},
        ]}
        with mock.patch("app.infrastructure.elevenlabs.requests") as http:
            http.get.return_value = mock.Mock(status_code=200, ok=True, json=mock.Mock(return_value=payload))
            voices = ElevenLabsClient(lambda: "k").voices()
        self.assertEqual([v.label for v in voices], ["Rachel — american ♀ — ElevenLabs", "Sin datos — ElevenLabs"])
        self.assertEqual(voices[0].preview, "https://x/r.mp3")


class ClientTests(unittest.TestCase):
    def reply(self, status=200, payload=None):
        response = mock.Mock(status_code=status, ok=status < 400, text="")
        response.json.return_value = payload or {}
        return response

    def test_speak_writes_the_audio_and_returns_the_words(self):
        audio = base64.b64encode(b"ID3audio").decode()
        with tempfile.TemporaryDirectory() as tmp, mock.patch("app.infrastructure.elevenlabs.requests") as http:
            http.post.return_value = self.reply(payload={"audio_base64": audio, "alignment": ALIGNMENT})
            out = Path(tmp) / "v.mp3"
            words = ElevenLabsClient(lambda: "k").speak("Hola mundo", "eleven:abc", "+8%", out)
            self.assertEqual(out.read_bytes(), b"ID3audio")
            self.assertEqual(len(words), 2)
            call = http.post.call_args
            self.assertTrue(call.args[0].endswith("/text-to-speech/abc/with-timestamps"))
            self.assertEqual(call.kwargs["headers"], {"xi-api-key": "k"})
            self.assertEqual(call.kwargs["json"]["model_id"], "eleven_multilingual_v2")
            self.assertEqual(call.kwargs["json"]["voice_settings"], {"speed": 1.08})

    def test_without_a_key_it_says_so(self):
        with self.assertRaises(EngineError) as raised:
            ElevenLabsClient(lambda: None).speak("Hola", "eleven:abc", "+0%", Path("x.mp3"))
        self.assertIn("clave", str(raised.exception))

    def test_a_rejected_key_and_no_credits_are_told_apart(self):
        for status, expected in ((401, "no aceptó la clave"), (402, "créditos")):
            with mock.patch("app.infrastructure.elevenlabs.requests") as http:
                http.post.return_value = self.reply(status=status)
                with self.assertRaises(EngineError) as raised:
                    ElevenLabsClient(lambda: "k").speak("Hola", "eleven:abc", "+0%", Path("x.mp3"))
                self.assertIn(expected, str(raised.exception))


class RejectedKeyTests(unittest.TestCase):
    def test_the_reason_elevenlabs_gives_is_shown(self):
        denied = mock.Mock(status_code=401, ok=False, text="")
        denied.json.return_value = {"detail": {"status": "missing_permissions", "message": "falta el permiso voices_read"}}
        with mock.patch("app.infrastructure.elevenlabs.requests") as http:
            http.get.return_value = denied
            with self.assertRaises(EngineError) as raised:
                ElevenLabsClient(lambda: "k").voices()
        self.assertEqual(str(raised.exception), "ElevenLabs no aceptó la clave: falta el permiso voices_read")


class RouterTests(unittest.TestCase):
    def test_each_voice_goes_to_its_provider(self):
        gen, eleven = mock.Mock(), mock.Mock()
        gen.synthesize_voice.return_value = ["edge"]
        eleven.speak.return_value = ["eleven"]
        router = VoiceRouter(gen, eleven)
        out = Path("x.mp3")
        self.assertEqual(router.synthesize_voice("Hola", "es-MX-DaliaNeural", "+8%", "+0Hz", out), ["edge"])
        self.assertEqual(router.synthesize_voice("Hola", "eleven:abc", "+8%", "+0Hz", out), ["eleven"])
        gen.synthesize_voice.assert_called_once_with("Hola", "es-MX-DaliaNeural", "+8%", "+0Hz", out)
        eleven.speak.assert_called_once_with("Hola", "eleven:abc", "+8%", out)

    def test_an_elevenlabs_voice_without_a_client_is_an_error_not_an_edge_voice(self):
        with self.assertRaises(EngineError):
            VoiceRouter(mock.Mock(), None).synthesize_voice("Hola", "eleven:abc", "+0%", "+0Hz", Path("x.mp3"))


class CatalogTests(unittest.TestCase):
    def test_without_a_key_only_edge_voices(self):
        studio, fakes = make_studio()
        voices = studio.voices.all()
        self.assertEqual({v.provider for v in voices}, {"edge"})
        self.assertFalse(studio.voices.elevenlabs()["ready"])
        self.assertEqual(fakes.eleven.calls, 0)

    def test_with_a_key_both_providers_live_together_and_the_list_is_cached(self):
        studio, fakes = make_studio(DictCredentials(ELEVENLABS_API_KEY="k"))
        voices = studio.voices.all()
        self.assertEqual([v.id for v in voices if v.provider == "elevenlabs"], ["eleven:abc123", "eleven:def456"])
        self.assertEqual(voices[0].provider, "edge")
        studio.voices.all()
        self.assertEqual(fakes.eleven.calls, 1)

    def test_a_failing_account_keeps_edge_voices_and_says_why(self):
        studio, fakes = make_studio(DictCredentials(ELEVENLABS_API_KEY="mala"))
        fakes.eleven.problem = EngineError("ElevenLabs no aceptó la clave.")
        self.assertEqual({v.provider for v in studio.voices.all()}, {"edge"})
        self.assertEqual(studio.voices.elevenlabs()["problem"], "ElevenLabs no aceptó la clave.")


class RefreshTests(unittest.TestCase):
    def test_refreshing_asks_the_account_again_instead_of_using_the_saved_list(self):
        studio, fakes = make_studio(DictCredentials(ELEVENLABS_API_KEY="k"))
        studio.voices.all()
        studio.voices.all()
        self.assertEqual(fakes.eleven.calls, 1)
        studio.voices.refresh()
        studio.voices.all()
        self.assertEqual(fakes.eleven.calls, 2)  # una sola consulta nueva: `all` reutiliza la que trajo `refresh`


class ApiTests(unittest.TestCase):
    def setUp(self):
        studio, self.fakes = make_studio()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
        paths = Paths(root=root, generator=root, data=root)
        self.client = TestClient(create_app(Container(studio=studio, paths=paths, workers=[])))

    def test_saving_the_key_adds_the_account_voices_to_the_config(self):
        before = self.client.get("/api/config").json()
        self.assertFalse(before["elevenlabs"]["ready"])
        saved = self.client.post("/api/elevenlabs", json={"api_key": " sk_123 "}).json()
        self.assertTrue(saved["elevenlabs"]["ready"])
        self.assertIn("eleven:abc123", [v["id"] for v in saved["voices"]])
        removed = self.client.post("/api/elevenlabs", json={"api_key": ""}).json()
        self.assertFalse(removed["elevenlabs"]["ready"])
        self.assertEqual({v["provider"] for v in removed["voices"]}, {"edge"})

    def test_trying_a_voice_says_the_sample_phrase_with_that_voice_and_is_reused(self):
        first = self.client.post("/api/samples", json={"voice": "eleven:abc123", "rate": "+0%"}).json()
        again = self.client.post("/api/samples", json={"voice": "eleven:abc123", "rate": "+0%"}).json()
        self.assertEqual(first["key"], again["key"])
        requests = self.fakes.sample_synthesizer.requests
        self.assertEqual(len(requests), 1)
        self.assertEqual((requests[0].text, requests[0].voice), (SAMPLE_TEXT, "eleven:abc123"))
        self.assertEqual(self.fakes.synthesizer.requests, [])  # no toca las tomas de los guiones
        other = self.client.post("/api/samples", json={"voice": "es-MX-JorgeNeural"}).json()
        self.assertNotEqual(first["key"], other["key"])

    def test_a_key_with_spaces_inside_is_refused(self):
        self.assertEqual(self.client.post("/api/elevenlabs", json={"api_key": "sk 123"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
