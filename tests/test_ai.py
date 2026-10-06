import json
import urllib.error
from unittest import mock

import config
from ai.gemini_service import GeminiClient, _grounded, rule_based_intent
from exceptions.custom_exceptions import AIServiceError
from tests.helpers import BackendCase

A, B = "NC-SI-000001", "NC-SI-000002"


def reply(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class RuleTests(BackendCase):
    def test_intents(self):
        cases = {
            "Who has card 047?": ("card_holder", "047"),
            "Who currently has card #47": ("card_holder", "47"),
            "Who was the last person assigned card 023?": ("card_last_holder", "023"),
            "Which guest cards haven't been returned?": ("unreturned_cards", None),
            "Who was last assigned a missing card?": ("missing_cards", None),
            "How many cards are free?": ("available_cards", None),
            "Which interns are currently inside?": ("inside_interns", None),
            "Give me today's attendance summary.": ("attendance_summary", None),
            "tell me about NC-NY-000101": ("find_intern", None),
            "what is the meaning of life": ("unknown", None),
        }
        for question, (intent, card) in cases.items():
            got, params = rule_based_intent(question)
            self.assertEqual((got, params["card_id"]), (intent, card), question)


class LocalAnswerTests(BackendCase):
    """No API key: everything is answered from the real records with templates."""
    def test_card_holder_and_last_holder(self):
        self.svc.gate.check_in(A)
        self.assertIn("Raymond Udoh", self.svc.ask("Who has card 1?"))
        self.svc.gate.check_out(A)
        self.assertIn("not issued", self.svc.ask("Who has card 001?"))
        self.assertIn("last held by Raymond Udoh", self.svc.ask("Who was last assigned card 001?"))
        self.assertIn("never been assigned", self.svc.ask("Who was last assigned card 002?"))

    def test_lists(self):
        self.svc.gate.check_in(A)
        self.svc.gate.check_in(B)
        self.assertIn("2 inside", self.svc.ask("Who is inside?"))
        self.svc.gate.check_out(B, card_returned=False)
        answer = self.svc.ask("Which cards haven't been returned?")
        self.assertIn("2 unreturned", answer)
        self.svc.cards.mark_card_missing("001")
        self.assertIn("001", self.svc.ask("Which cards are missing?"))

    def test_errors_are_sentences_not_crashes(self):
        self.assertIn(f"001 to {config.CARD_COUNT:03d}", self.svc.ask("Who has card 999?"))
        self.assertIn("Which card", self.svc.queries._run("card_holder", {"card_id": None})["error"])
        self.assertIn("I can tell you", self.svc.ask("Who was the last person to hold the card assigned before"))
        self.assertTrue(self.svc.ask("hello there"))
        self.assertEqual(self.svc.ask("   "), "Type a question first.")

    def test_memo_is_cached_until_numbers_change(self):
        first = self.svc.memo()
        self.assertIn("DAILY ATTENDANCE MEMO", first)
        self.assertIs(self.svc.memo(), first)
        self.svc.gate.check_in(A)
        self.assertNotEqual(self.svc.memo(), first)


class GeminiTests(BackendCase):
    def gemini(self, *responses):
        calls = []

        def transport(url, headers, body, timeout):
            calls.append(body)
            r = responses[min(len(calls), len(responses)) - 1]
            if isinstance(r, Exception):
                raise r
            return r
        return GeminiClient(api_key="test-key", transport=transport), calls

    def test_gemini_routes_then_python_looks_up_then_gemini_phrases(self):
        self.svc.gate.check_in(A)
        g, calls = self.gemini(reply(json.dumps({"intent": "card_holder", "card_id": "001"})),
                               reply("Card 001 is currently with Raymond Udoh."))
        svc = self.restart(gemini=g)
        self.assertEqual(svc.ask("whose card is number one?"), "Card 001 is currently with Raymond Udoh.")
        self.assertEqual(len(calls), 2)
        facts = calls[1]["contents"][0]["parts"][0]["text"]         # the AI is only given real records
        self.assertIn("Raymond Udoh", facts)
        self.assertIn("ONLY", calls[1]["systemInstruction"]["parts"][0]["text"])

    def test_every_failure_falls_back_to_local_answers(self):
        self.svc.gate.check_in(A)
        failures = [urllib.error.URLError("offline"), TimeoutError(), OSError("boom"),
                    urllib.error.HTTPError("u", 503, "unavailable", {}, None),
                    {"unexpected": "shape"}, reply("")]
        for failure in failures:
            g, _ = self.gemini(failure)
            svc = self.restart(gemini=g)
            self.assertIn("Raymond Udoh", svc.ask("Who has card 1?"), failure)

    def test_bad_router_json_uses_rules_but_ai_still_phrases(self):
        self.svc.gate.check_in(A)
        g, _ = self.gemini(reply("not json at all"), reply("Card 001 is with Raymond Udoh."))
        self.assertEqual(self.restart(gemini=g).ask("Who has card 1?"), "Card 001 is with Raymond Udoh.")

    def test_ai_wording_that_invents_data_is_rejected(self):
        self.svc.gate.check_in(A)
        for lie in ("Card 001 is with Someone Else (NC-NY-000999).", "Card 042 is with Raymond Udoh."):
            g, _ = self.gemini(reply(json.dumps({"intent": "card_holder", "card_id": "001"})), reply(lie))
            answer = self.restart(gemini=g).ask("who has card 1")
            self.assertNotEqual(answer, lie)
            self.assertIn("Card 001 is with Raymond Udoh (NC-SI-000001)", answer)

    def test_grounding_does_not_accept_card_number_inside_an_intern_id(self):
        facts = json.dumps({"intern_id": "NC-SI-000001", "name": "Raymond Udoh"})

        self.assertFalse(_grounded("Card 001 is with Raymond Udoh.", facts))
        self.assertTrue(_grounded("Raymond Udoh is intern NC-SI-000001.", facts))

    def test_router_returning_an_invented_intent_is_ignored(self):
        self.svc.gate.check_in(A)
        g, _ = self.gemini(reply(json.dumps({"intent": "delete_everything"})), AIServiceError("x"))
        svc = self.restart(gemini=g)
        self.assertIn("Raymond Udoh", svc.ask("Who has card 1?"))

    def test_gemini_memo_and_markdown_stripped(self):
        g, calls = self.gemini(reply("**DAILY ATTENDANCE MEMO**\nAll quiet."))
        svc = self.restart(gemini=g)
        self.assertEqual(svc.memo(), "DAILY ATTENDANCE MEMO\nAll quiet.")
        svc.memo()
        self.assertEqual(len(calls), 1)

    def test_request_shape(self):
        g, calls = self.gemini(reply("ok"))
        g.generate("hi", system="sys", as_json=True)
        body = calls[0]
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "sys")

    def test_no_key_raises_ai_error(self):
        with self.assertRaises(AIServiceError):
            GeminiClient(api_key="").generate("hi")
