"""Gemini integration for administrative questions and the daily memo.

Architecture (Python owns the data, the AI only interprets and phrases):

    question -> Gemini picks an intent          (falls back to keyword rules if Gemini is unavailable)
             -> Python runs the matching lookup on the real records
             -> Gemini words the answer from those facts only   (falls back to a plain template)

Gemini never touches the JSON files and never decides who is inside or who holds a card.
Any AI failure (no key, timeout, bad JSON, HTTP error) is caught and the local answer is used.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date, datetime

import config
from exceptions.custom_exceptions import AIServiceError, GateError

log = logging.getLogger("gate")

INTENTS = ("card_holder", "card_last_holder", "unreturned_cards", "missing_cards",
           "available_cards", "inside_interns", "attendance_summary", "find_intern")
HELP = ("I can tell you who holds a card, who last had it, which cards are unreturned or missing, "
        "who is inside, or write the daily memo.")

SYSTEM_ROUTER = """You route questions for a building gate and guest-card system to exactly one function.
Reply with JSON only, no markdown:
{"intent": "<intent>", "card_id": "<digits or null>", "intern_id": "<NC-NY-###### or NC-SI-###### or null>", "name": "<person name or null>"}
Intents:
card_holder: who has / is holding a given card now.
card_last_holder: who was last assigned / previously had a given card.
unreturned_cards: which cards have not been returned.
missing_cards: which cards are missing or lost, and who last had them.
available_cards: how many / which cards are free.
inside_interns: who is inside the building now.
attendance_summary: today's attendance summary or memo.
find_intern: details about one intern (by ID or name).
unknown: anything else."""

SYSTEM_ANSWER = ("You are the assistant of the NCAIR gate attendance system. Answer the administrator's question "
                 "using ONLY the JSON facts provided. Never invent names, card numbers or times. Be brief and "
                 "use plain text with no markdown.")

SYSTEM_MEMO = ("Write a short professional daily attendance memo for the NCAIR E-Government Facility administration "
               "using ONLY the JSON facts provided. Plain text, no markdown, under 150 words. Start with the title "
               "'DAILY ATTENDANCE MEMO' and the date. Never invent figures.")

CARD_RE = re.compile(r"\bcard\s*(?:no\.?|number|num|#)?\s*#?\s*(\d{1,3})\b")


# ---- Gemini over plain HTTPS (no SDK needed) -----------------------------------
def _http_post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


class GeminiClient:
    def __init__(self, api_key=config.GEMINI_API_KEY, model=config.GEMINI_MODEL,
                 timeout=config.GEMINI_TIMEOUT, transport=_http_post):
        self.api_key, self.model, self.timeout, self.transport = api_key, model, timeout, transport

    @property
    def available(self):
        return bool(self.api_key)

    def generate(self, prompt, system=None, as_json=False):
        """Return the model's text. Raises AIServiceError on any failure."""
        if not self.available:
            raise AIServiceError("No Gemini API key is set.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if as_json:
            body["generationConfig"]["responseMimeType"] = "application/json"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        try:
            data = self.transport(url, headers, body, self.timeout)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            raise AIServiceError(f"Gemini returned HTTP {e.code}.") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise AIServiceError(f"Could not reach Gemini: {e}") from e
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise AIServiceError(f"Unexpected Gemini response: {e!r}") from e
        if not str(text).strip():
            raise AIServiceError("Gemini returned an empty answer.")
        return str(text).strip()


# ---- keyword fallback ------------------------------------------------------------
def rule_based_intent(question, interns=()):
    """Cheap local intent detection used when Gemini is unavailable. Returns (intent, params)."""
    t = question.lower()
    params = {"card_id": None, "intern_id": None, "name": None}
    m = re.search(r"nc-?(ny|si)-?(\d{6})", t)
    if m:
        params["intern_id"] = f"NC-{m.group(1).upper()}-{m.group(2)}"
        return "find_intern", params
    m = CARD_RE.search(t)
    if m:
        params["card_id"] = m.group(1)
    if re.search(r"unreturned|not (been )?returned|haven'?t (been )?returned|outstanding|yet to (be )?return", t):
        return "unreturned_cards", params
    if re.search(r"missing|\blost\b|misplaced", t):
        return "missing_cards", params
    if params["card_id"]:
        if re.search(r"\blast\b|previous|prior|before|earlier|was assigned|were assigned|used to", t):
            return "card_last_holder", params
        return "card_holder", params
    if "card" in t and re.search(r"available|free|spare|left|remaining|how many", t):
        return "available_cards", params
    if re.search(r"inside|in the (building|facility)|present|on site|currently in", t):
        return "inside_interns", params
    if re.search(r"summary|memo|report|attendance|today|how many", t):
        return "attendance_summary", params
    for i in interns:
        tokens = i.name.lower().split()[:2]
        if tokens and all(tok in t for tok in tokens):
            params["name"] = i.name
            return "find_intern", params
    return "unknown", params


def _parse_json(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    return data


def _grounded(text, facts_json):
    """Check AI-mentioned IDs and three-digit numbers against exact fact tokens."""
    try:
        facts = json.loads(facts_json)
    except (TypeError, ValueError):
        return False

    fact_ids = set()
    fact_numbers = set()

    def collect_tokens(value):
        if isinstance(value, dict):
            for child in value.values():
                collect_tokens(child)
        elif isinstance(value, list):
            for child in value:
                collect_tokens(child)
        elif isinstance(value, str):
            fact_ids.update(re.findall(r"NC-(?:NY|SI)-[0-9]{6}", value))
            if re.fullmatch(r"[0-9]{3}", value):
                fact_numbers.add(value)
        elif isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 999:
            fact_numbers.add(str(value))

    collect_tokens(facts)
    answer_ids = set(re.findall(r"NC-(?:NY|SI)-[0-9]{6}", text))
    answer_numbers = set(re.findall(r"\b[0-9]{3}\b", text))
    return answer_ids <= fact_ids and answer_numbers <= fact_numbers


def _when(ts):
    return datetime.fromisoformat(ts).strftime("%H:%M on %d %b") if ts else "an unknown time"


class AdminQueryService:
    def __init__(self, gate, interns, cards, gemini):
        self.gate, self.interns, self.cards, self.gemini = gate, interns, cards, gemini
        self._memo_key = self._memo_text = None

    # ---- public --------------------------------------------------------------------
    def ask(self, question):
        """Answer a plain-language question. Never raises."""
        question = (question or "").strip()
        if not question:
            return "Type a question first."
        try:
            intent, params = self._interpret(question)
            if intent not in INTENTS:
                return HELP
            facts = self._run(intent, params)
            if "error" in facts:
                return facts["error"]
            return self._present(question, facts)
        except Exception:                                   # last safety net: the GUI must not crash
            log.exception("Unexpected failure while answering %r", question)
            return "Sorry, I could not answer that. The problem was logged."

    def memo(self):
        """Daily attendance memo. Cached until the underlying numbers change."""
        try:
            facts = self.gate.attendance_summary()
            key = json.dumps(facts, sort_keys=True)
            if key == self._memo_key:
                return self._memo_text
            text = None
            if self.gemini.available:
                try:
                    text = re.sub(r"[*#`]", "", self.gemini.generate(json.dumps(facts), SYSTEM_MEMO))
                except AIServiceError as e:
                    log.warning("Gemini memo failed, using the local memo: %s", e)
            self._memo_key, self._memo_text = key, text or self._local_memo(facts)
            return self._memo_text
        except Exception:
            log.exception("Memo generation failed")
            return "The memo could not be generated. The problem was logged."

    # ---- steps ---------------------------------------------------------------------
    def _interpret(self, question):
        if self.gemini.available:
            try:
                data = _parse_json(self.gemini.generate(question, SYSTEM_ROUTER, as_json=True))
                if data.get("intent") in INTENTS:
                    return data["intent"], {k: data.get(k) for k in ("card_id", "intern_id", "name")}
            except (AIServiceError, ValueError) as e:
                log.warning("Gemini routing failed, using keyword rules: %s", e)
        return rule_based_intent(question, self.interns.get_all_interns())

    def _person(self, intern_id):
        if not intern_id:
            return None
        i = self.interns.get(intern_id)
        return {"id": intern_id, "name": i.name if i else "unknown intern"}

    def _run(self, intent, params):
        """Run the real lookup. Returns a facts dict, or {"error": text} for a controlled failure."""
        try:
            if intent in ("card_holder", "card_last_holder"):
                if not params.get("card_id"):
                    return {"error": "Which card? For example: Who has card 047?"}
                c = self.cards.get_card(params["card_id"])
                if intent == "card_holder":
                    return {"intent": intent, "card": c.card_id, "status": c.status,
                            "holder": self._person(c.current_holder), "assigned_at": c.assigned_at,
                            "previous_holder": self._person(c.previous_holder)}
                return {"intent": intent, "card": c.card_id, "status": c.status,
                        "last_holder": self._person(c.last_holder), "still_holding": bool(c.current_holder),
                        "assigned_at": c.assigned_at, "returned_at": c.returned_at}
            if intent in ("unreturned_cards", "missing_cards"):
                cards = (self.cards.get_unreturned_cards() if intent == "unreturned_cards"
                         else self.cards.get_missing_cards())
                rows = []
                for c in cards:
                    holder = self.interns.get(c.current_holder)
                    rows.append({"card": c.card_id, "status": c.status, "last_holder": self._person(c.last_holder),
                                 "holder_is_inside": bool(holder and holder.is_inside), "assigned_at": c.assigned_at})
                return {"intent": intent, "count": len(rows), "cards": rows}
            if intent == "available_cards":
                s = self.cards.stats()
                return {"intent": intent, "available": s["available"], "total": s["total"]}
            if intent == "inside_interns":
                held = self.cards.holders_map()
                people = [{"id": i.intern_id, "name": i.name,
                           "card": held[i.intern_id].card_id if i.intern_id in held else None}
                          for i in self.gate.get_inside_interns()]
                return {"intent": intent, "count": len(people), "people": people}
            if intent == "attendance_summary":
                return {"intent": intent, **self.gate.attendance_summary()}
            if intent == "find_intern":
                if params.get("intern_id"):
                    found = [self.interns.find_intern(params["intern_id"])]
                elif params.get("name"):
                    found = self.interns.search(params["name"])[:5]
                else:
                    return {"error": "Which intern? Give a name or an ID."}
                if not found:
                    return {"error": f"No intern matches {params.get('name')!r}."}
                held = self.cards.holders_map()
                return {"intent": intent, "matches": [
                    {"id": i.intern_id, "name": i.name, "programme": i.programme, "department": i.department,
                     "status": i.status, "card": held[i.intern_id].card_id if i.intern_id in held else None}
                    for i in found]}
        except GateError as e:
            return {"error": str(e)}
        return {"error": HELP}

    def _present(self, question, facts):
        if self.gemini.available:
            facts_json = json.dumps(facts)
            try:
                text = self.gemini.generate(f"Question: {question}\nFacts: {facts_json}", SYSTEM_ANSWER)
                if _grounded(text, facts_json):
                    return text
                log.warning("Gemini mentioned data that is not in the records; using the local answer.")
            except AIServiceError as e:
                log.warning("Gemini phrasing failed, using the local answer: %s", e)
        return self._local_answer(facts)

    # ---- plain-template answers (also the fallback) -------------------------------
    @staticmethod
    def _who(p):
        return f"{p['name']} ({p['id']})" if p else "nobody"

    def _local_answer(self, f):
        intent = f["intent"]
        if intent == "card_holder":
            if f["holder"]:
                return f"Card {f['card']} is with {self._who(f['holder'])}, issued at {_when(f['assigned_at'])}."
            prev = f" It was last held by {self._who(f['previous_holder'])}." if f["previous_holder"] else ""
            return f"Card {f['card']} is not issued right now ({f['status'].lower()}).{prev}"
        if intent == "card_last_holder":
            if not f["last_holder"]:
                return f"Card {f['card']} has never been assigned."
            if f["still_holding"]:
                return f"Card {f['card']} was last assigned to {self._who(f['last_holder'])} at {_when(f['assigned_at'])} and is still with them."
            return f"Card {f['card']} was last held by {self._who(f['last_holder'])} and returned at {_when(f['returned_at'])}."
        if intent in ("unreturned_cards", "missing_cards"):
            label = "unreturned" if intent == "unreturned_cards" else "missing"
            if not f["count"]:
                return f"No cards are {label}."
            lines = [f"{c['card']}: {self._who(c['last_holder'])}" + (" (inside)" if c["holder_is_inside"] else "")
                     + (" [MISSING]" if c["status"] == "MISSING" else "") for c in f["cards"]]
            return f"{f['count']} {label} card(s): " + "; ".join(lines) + "."
        if intent == "available_cards":
            return f"{f['available']} of {f['total']} guest cards are free."
        if intent == "inside_interns":
            if not f["count"]:
                return "Nobody is inside right now."
            return f"{f['count']} inside: " + ", ".join(p["name"] for p in f["people"]) + "."
        if intent == "attendance_summary":
            return self._local_memo(f)
        m = f["matches"]
        return " | ".join(f"{i['name']} ({i['id']}), {i['programme']}, {i['department']}: {i['status'].lower()}"
                          + (f", card {i['card']}" if i["card"] else "") for i in m)

    @staticmethod
    def _local_memo(s):
        day = date.fromisoformat(s["date"]).strftime("%a %d %b %Y")
        lines = [f"DAILY ATTENDANCE MEMO \u00b7 {day}", "",
                 f"{s['check_ins']} check-ins and {s['check_outs']} check-outs recorded today.",
                 f"{s['inside_now']} of {s['total_interns']} interns are inside now "
                 f"({s['inside_nysc']} NYSC, {s['inside_siwes']} SIWES).",
                 f"Guest cards: {s['cards_issued']} issued, {s['cards_free']} free of {s['cards_total']}.",
                 f"Cards not returned by interns who have left: {s['cards_unreturned_after_leaving']}. "
                 f"Marked missing: {s['cards_missing']}."]
        if s["first_check_in"]:
            lines.append(f"First check-in {s['first_check_in']}, last movement {s['last_movement']}.")
        return "\n".join(lines)
