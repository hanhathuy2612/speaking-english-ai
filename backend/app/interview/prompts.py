"""LLM prompt and the NOTE guard. Rationale for each decision: docs/features/llm-prompt.md."""

from __future__ import annotations

from app.core.config import MAX_HISTORY
from app.interview.session import Session, followup_limit
from app.utils.compare import invented_facts
from app.utils.parsing import has_cjk, norm

# Interview units use DEFAULT_ROLE, which renders exactly the prompt validated with replay.py.
# Conversation units set "role" in units.json (docs/features/conversation-mode.md).
DEFAULT_ROLE = "the INTERVIEWER in a job interview"

SYSTEM_TEMPLATE = """You play {role}. The candidate is a learner practising spoken English. Each user message gives the current question and the candidate's latest answer.

Never talk about your own job or experience. Never say a first-person sentence that sounds like the candidate's answer. Speak to the candidate as "you".

Scenario: {scenario}

Reply in EXACTLY this format, four lines, no markdown:
RETRY: yes or no
SAY: <one short reaction to the answer, second person, under 15 words, not a question>
ASK: <one question, or NEXT>
NOTE: <one improved version of the candidate's key sentence, first person, under 25 words>

Rules:
- RETRY is yes only if the answer is off-topic, only a few words, not English, or does not make sense (probably misheard). Grammar mistakes do NOT count.
- SAY and ASK respond ONLY to the latest answer, never to earlier ones.
- If RETRY is yes: SAY is a polite "sorry, I didn't quite catch that". ASK is NEXT (the app repeats the question).
- If RETRY is no: ASK is NEXT, unless "Follow-up allowed: yes" and the answer mentions one detail worth asking about. Then ASK is one short follow-up question about that detail.
- NOTE fixes the candidate's grammar and wording, keeps their meaning, and uses the target phrase when it fits. If RETRY is yes, NOTE is a short model answer to the current question using the target phrase.
- NOTE uses ONLY facts the candidate said in this interview. Never invent numbers, names, results or tasks. If a fact is missing, write "..." in its place.
- Never use Vietnamese.

Phrases the candidate is practising:
{phrases}"""

# Few-shot examples deliberately use a different job (logistics) so the model does not copy them
# into the real conversation.
# If you change the job in the examples, update EXAMPLE_WORDS.
FEW_SHOT = [
    {
        "role": "user",
        "content": "Current question: Could you tell me a little about yourself?\n"
        "Target phrase: I've been working as a ... for ... years.\n"
        "Follow-up allowed: yes\n"
        "Latest answer: I am work in logistic company since four year, I manage the delivery schedule.",
    },
    {
        "role": "assistant",
        "content": "RETRY: no\n"
        "SAY: So you manage delivery schedules, that's an important job.\n"
        "ASK: How many deliveries do you plan in a typical week?\n"
        "NOTE: I've been working at a logistics company for four years, and I manage the delivery schedule.",
    },
    {
        "role": "user",
        "content": "Current question: What is one achievement you're proud of?\n"
        "Target phrase: One of my main achievements was ...\n"
        "Follow-up allowed: no\n"
        "Latest answer: We have problem with late delivery, I change the route plan and late delivery go down thirty percent.",
    },
    {
        "role": "assistant",
        "content": "RETRY: no\n"
        "SAY: Cutting late deliveries by thirty percent is a great result.\n"
        "ASK: NEXT\n"
        "NOTE: One of my main achievements was redesigning our route plan, which cut late deliveries by thirty percent.",
    },
    {
        "role": "user",
        "content": "Earlier in the interview:\n"
        "- Q: Could you tell me a little about yourself? A: I am coordinator in logistic company, four year.\n"
        "Current question: What are you mainly responsible for in your current role?\n"
        "Target phrase: I'm responsible for ...\n"
        "Follow-up allowed: yes\n"
        "Latest answer: Come responsible for the schedule also",
    },
    {
        "role": "assistant",
        "content": "RETRY: yes\n"
        "SAY: Sorry, I didn't quite catch that.\n"
        "ASK: NEXT\n"
        "NOTE: As a logistics coordinator, I'm responsible for ... and ...",
    },
]

EXAMPLE_WORDS = ("logistic", "deliver", "route", "coordinator", "driver")  # words that appear in FEW_SHOT


def target_phrases(unit: dict, q_index: int) -> list[str]:
    return [unit["phrases"][i]["say"] for i in unit["questions"][q_index]["phrases"]]


def build_messages(s: Session, answer: str) -> list[dict]:
    phrases = "\n".join(f"- {p['say']}" for p in s.unit["phrases"])
    system = SYSTEM_TEMPLATE.format(
        role=s.unit.get("role", DEFAULT_ROLE), scenario=s.unit["scenario"], phrases=phrases
    )
    return [
        {"role": "system", "content": system},
        *FEW_SHOT,
        {"role": "user", "content": build_user_message(s, answer)},
    ]


def build_user_message(s: Session, answer: str) -> str:
    lines = []
    earlier = s.history[-MAX_HISTORY:] if MAX_HISTORY else []
    if earlier:
        lines.append("Earlier in the interview:")
        lines += [f"- Q: {h['q']} A: {h['a']}" for h in earlier]
    # Latest answer goes last: the 7B model tends to react to whatever it read most recently.
    main = s.unit["questions"][s.q]
    on_follow_up = s.asked not in (main["ask"], main["simple"])
    # On a follow-up the main question's phrase usually does not fit, and the model then rewrote
    # an EARLIER answer to use it instead of improving the latest one.
    target = "none (follow-up question)" if on_follow_up else " / ".join(target_phrases(s.unit, s.q))
    lines += [
        f"Current question: {s.asked}",
        f"Target phrase: {target}",
        f"Follow-up allowed: {'yes' if s.followups < followup_limit(s.unit) else 'no'}",
        f"Latest answer: {answer}",
    ]
    return "\n".join(lines)


def safe_note(s: Session, q_index: int, note: str, retry: bool) -> str:
    """Replace a NOTE that leaks few-shot content, changes the learner's facts (numbers, days,
    dates), drifts into Chinese, or is made up before we know anything about the learner, with the target phrase template."""
    said = " ".join(h["a"] for h in s.history)
    known = norm(said)
    leaked = any(w in norm(note) and w not in known for w in EXAMPLE_WORDS)
    # The model sometimes "corrects" details ("tomorrow" -> "on Friday"); reading that aloud
    # would teach a false sentence. Facts from the target phrase itself are allowed.
    changed = bool(invented_facts(note, f"{said} {' '.join(target_phrases(s.unit, q_index))}"))
    no_facts = retry and len(s.history) <= 1  # only the latest (unclear) answer is known
    # A NOTE is a first-person sentence to say; "You enjoy ..." is the model talking about the learner.
    second_person = norm(note).startswith("you ")
    if note and not (leaked or changed or no_facts or second_person or has_cjk(note)):
        return note
    return " ".join(target_phrases(s.unit, q_index))
