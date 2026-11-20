import json
import unittest

from app.application.use_cases.growth import GrowthUseCases
from app.application.use_cases.prompts import PromptBook
from app.domain.errors import ValidationError, WriterError
from app.domain.events import GROWTH_COMPLETED, GROWTH_FAILED, GROWTH_REQUESTED
from app.domain.growth import KINDS, kind_by_id, parse_growth
from tests.fakes import DictCredentials, FakeComposer, make_studio

REPLIES = {
    "hooks": {"hooks": [{"text": "¿Sabías esto?", "type": "Pregunta", "why": "intriga"}, {"text": ""}]},
    "retention": {"score": 140, "summary": "Flojo al medio", "issues": [{"at": "frase 3", "problem": "larga", "fix": "córtala"}]},
    "titles": {"titles": [{"text": "A", "score": 40, "why": "x"}, {"text": "B", "score": "88", "why": "y"}]},
    "seo": {"score": 55, "improved": "  Una   descripción\n\n #tag ", "tags": ["#Uno", "dos"], "tips": ["más clave"]},
    "score": {"total": 71, "parts": [{"name": "Gancho", "score": 80, "note": "ok"}], "actions": ["a", "b"]},
    "apply": {"summary": "Gancho nuevo", "script": "Nuevo gancho. El guion.", "title": None, "description": None},
    "trends": {"ideas": [{"title": "Idea", "angle": "a", "why": "w", "hook": "h"}], "trends": [{"topic": "t", "why": "w"}]},
}


class ParseTests(unittest.TestCase):
    def test_every_kind_cleans_its_reply(self):
        for kind in KINDS:
            result = parse_growth(kind, "<think>x</think>```json\n" + json.dumps(REPLIES[kind.id]) + "\n```")
            self.assertTrue(result, kind.id)

    def test_scores_are_clamped_and_titles_sorted(self):
        self.assertEqual(parse_growth(kind_by_id("retention"), json.dumps(REPLIES["retention"]))["score"], 100)
        titles = parse_growth(kind_by_id("titles"), json.dumps(REPLIES["titles"]))["titles"]
        self.assertEqual([t["text"] for t in titles], ["B", "A"])
        self.assertEqual(titles[0]["score"], 88)

    def test_empty_items_are_dropped_and_tags_normalised(self):
        self.assertEqual(len(parse_growth(kind_by_id("hooks"), json.dumps(REPLIES["hooks"]))["hooks"]), 1)
        seo = parse_growth(kind_by_id("seo"), json.dumps(REPLIES["seo"]))
        self.assertEqual(seo["tags"], ["uno", "dos"])
        self.assertEqual(seo["improved"], "Una descripción\n\n #tag".replace(" #", "#"))

    def test_garbage_is_rejected(self):
        for raw in ("hola", "", "{}", '{"hooks": []}'):
            with self.assertRaises(WriterError):
                parse_growth(kind_by_id("hooks"), raw)
        with self.assertRaises(ValidationError):
            kind_by_id("nada")


class GrowthTests(unittest.TestCase):
    def _studio(self, kind="hooks"):
        return make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer(json.dumps(REPLIES[kind])))

    def test_request_needs_what_the_kind_analyses_and_a_writer(self):
        studio, f = make_studio()
        with self.assertRaisesRegex(ValidationError, "tema o el guion"):
            studio.growth.request("hooks", " ")
        with self.assertRaisesRegex(ValidationError, "guion"):
            studio.growth.request("retention", "tema")
        with self.assertRaisesRegex(ValidationError, "Modelo del guion"):
            studio.growth.request("hooks", "tema")
        self.assertEqual(f.events.events, [])

    def test_it_is_advised_once_with_everything_known(self):
        studio, f = self._studio("score")
        event = studio.growth.request("score", " Sueño ", "**El** guion.", "Lo que *nadie* dice", " desc ", "45s")
        self.assertEqual(event.topic, GROWTH_REQUESTED)
        self.assertTrue(event.key.startswith("gr-"))
        self.assertEqual(event.payload["title"], "Lo que nadie dice")
        studio.growth.handle_request(event)
        studio.growth.handle_request(event)
        (_, _, key, system, prompt), = f.composer.calls
        self.assertEqual(key, "nv")
        self.assertIn("0 a 100", system)
        for part in ("Tema: Sueño", "Duración objetivo: 45s", "Título actual: Lo que nadie dice", "El guion.", "desc"):
            self.assertIn(part, prompt)
        self.assertEqual(f.events.events[-1].topic, GROWTH_COMPLETED)
        outcome = studio.outcome(event.key)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(outcome["result"]["total"], 71)

    def test_a_broken_reply_fails_with_the_reason(self):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer("no es json"))
        event = studio.growth.request("hooks", "tema")
        studio.growth.handle_request(event)
        self.assertEqual(f.events.events[-1].topic, GROWTH_FAILED)
        self.assertIn("no se pudo leer", studio.outcome(event.key)["detail"])

    def test_an_edited_prompt_reaches_the_model(self):
        studio, f = self._studio()
        book = PromptBook()
        growth = GrowthUseCases(f.events, studio.writer, f.composer, book)
        book.save("growth_hooks", "Dame ganchos picantes. Solo JSON.")
        growth.handle_request(growth.request("hooks", "tema"))
        self.assertEqual(f.composer.calls[0][3], "Dame ganchos picantes. Solo JSON.")
        self.assertIn("growth_hooks", [p["id"] for p in book.catalog()])


class ApplyTests(unittest.TestCase):
    SCRIPT = "ANA: Hola.\nLUIS: Qué tal."

    def _run(self, reply, **given):
        studio, f = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer(json.dumps(reply)))
        args = {"topic": "Sueño", "script": self.SCRIPT, "title": "Lo que *nadie* dice", "description": "desc", **given}
        event = studio.growth.request(
            "apply", args["topic"], args["script"], args["title"], args["description"], "", "Abre con una pregunta",
        )
        studio.growth.handle_request(event)
        return studio.outcome(event.key), f

    def test_a_recommendation_is_required(self):
        studio, _ = make_studio(credentials=DictCredentials(NVIDIA_API_KEY="nv"), composer=FakeComposer("{}"))
        with self.assertRaisesRegex(ValidationError, "recomendación"):
            studio.growth.request("apply", "tema", "un guion", "", "", "", "  ")

    def test_the_model_sees_the_video_and_the_recommendation_and_a_dialogue_keeps_its_lines(self):
        _, f = self._run({"summary": "x", "script": None, "title": None, "description": None})
        prompt = f.composer.calls[0][4]
        self.assertIn("Recomendación a aplicar:\nAbre con una pregunta", prompt)
        self.assertIn("ANA: Hola.\nLUIS: Qué tal.", prompt)

    def test_only_what_really_changes_comes_back(self):
        outcome, _ = self._run({
            "summary": "Nuevo gancho",
            "script": "ANA: ¿Viste?\nLUIS: Qué tal.",
            "title": "Lo que nadie dice",  # igual que el de ahora, sin asteriscos
            "description": "desc",
        })
        result = outcome["result"]
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(result["script"], "ANA: ¿Viste?\nLUIS: Qué tal.")
        self.assertIsNone(result["title"])
        self.assertIsNone(result["description"])

    def test_a_recommendation_that_changes_nothing_is_a_valid_answer(self):
        for reply in (
            {"summary": "Se arregla publicando de noche", "script": None, "title": None, "description": None},
            {"summary": "Igual", "script": "ANA: Hola. LUIS: Qué tal.", "title": "null"},
        ):
            outcome, _ = self._run(reply)
            self.assertEqual(outcome["status"], "completed")
            self.assertEqual(
                {k: outcome["result"][k] for k in ("script", "title", "description")},
                {"script": None, "title": None, "description": None},
            )


class ReelsMethodTests(unittest.TestCase):
    def test_the_eight_piece_method_guides_writing_and_scoring(self):
        from app.domain.growth import APPLY_PROMPT, RETENTION_PROMPT, SCORE_PROMPT
        from app.domain.writer import system_prompt

        for prompt in (RETENTION_PROMPT, SCORE_PROMPT, APPLY_PROMPT):
            self.assertIn("bucle abierto", prompt)
            self.assertIn("llamada a la acción", prompt)
        self.assertIn("estructura", SCORE_PROMPT)
        self.assertIn("Bucle abierto", system_prompt())
