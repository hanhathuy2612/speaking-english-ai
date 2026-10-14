"""Lesson part of a unit: a teacher explains each sentence and the learner reads it aloud.

The app walks through the sentences in order; nothing here calls the LLM, and a reading is judged
only by word comparison (utils/compare.py). Content lives in the unit's `lesson` field
(data/units.json). See docs/features/lesson.md.
"""

from __future__ import annotations

from app.utils.parsing import has_vietnamese

# Fixed teacher lines shared by every lesson: English is spoken, Vietnamese is the on-screen translation.
TEACHER: dict[str, tuple[str, str]] = {
    "vocab": (
        "First, here are the key words for today.",
        "Trước hết, đây là các từ quan trọng của bài hôm nay.",
    ),
    "read": (
        "Could you please read that sentence aloud?",
        "Bạn đọc to câu đó giúp mình nhé.",
    ),
    "good": ("Great, that was clear!", "Tốt lắm, câu đó rõ rồi!"),
    "retry": (
        "Almost there. Listen once more and try again.",
        "Gần đúng rồi. Nghe lại một lần nữa rồi thử lại nhé.",
    ),
    "move_on": (
        "Good effort. Let's move on, and you can practise it again later.",
        "Cố gắng tốt. Mình sang câu tiếp, câu này bạn sẽ ôn lại sau.",
    ),
    "outro": (
        "Well done! You've learned all the sentences. Now let's use them in a role-play.",
        "Làm tốt lắm! Bạn đã học xong các câu. Giờ mình dùng chúng trong phần đóng vai nhé.",
    ),
}


def lines(unit: dict) -> dict[str, dict[str, str]]:
    """Every line the teacher can speak in this unit's lesson, by key: {"en", "vi"}.

    Keys: the TEACHER lines, "intro", "s<i>" (explanation + sentence i), "say<i>" (sentence i alone,
    replayed before a retry) and "w<i>" (vocabulary word i). The audio endpoint only speaks these,
    so arbitrary text never reaches the TTS cache.
    """
    lesson = unit["lesson"]
    out = {k: {"en": en, "vi": vi} for k, (en, vi) in TEACHER.items()}
    out["intro"] = {"en": lesson["intro"], "vi": lesson["intro_vi"]}
    if lesson.get("outro"):  # talk lessons end with practice, not a role-play (interview/talks.py)
        out["outro"] = {"en": lesson["outro"], "vi": lesson.get("outro_vi", "")}
    for i, s in enumerate(lesson["sentences"]):
        out[f"s{i}"] = {"en": f"{s['use']} {s['say']}", "vi": s["use_vi"]}
        out[f"say{i}"] = {"en": s["say"], "vi": ""}
    for i, w in enumerate(lesson["vocab"]):
        out[f"w{i}"] = {"en": w["word"], "vi": w["vi"]}
    return out


def validate(unit: dict) -> list[str]:
    """Problems in a unit's `lesson`; units without one are fine."""
    lesson = unit.get("lesson")
    if lesson is None:
        return []
    uid = unit.get("id", "?")
    errors = [f"{uid}: lesson needs {k}" for k in ("intro", "intro_vi", "vocab", "sentences") if not lesson.get(k)]
    if has_vietnamese(lesson.get("intro", "")):
        errors.append(f"{uid}: lesson intro must be in English (the teacher speaks it; intro_vi is the translation)")
    for i, w in enumerate(lesson.get("vocab", [])):
        if not (w.get("word") and w.get("vi")):
            errors.append(f"{uid}: lesson word {i} needs word and vi")
        if has_vietnamese(w.get("word", "")):
            errors.append(f"{uid}: lesson word {i} must be English (vi is the meaning)")
    n = len(unit.get("phrases", []))
    for i, s in enumerate(lesson.get("sentences", [])):
        if not (s.get("say") and s.get("use") and s.get("use_vi")):
            errors.append(f"{uid}: lesson sentence {i} needs say, use and use_vi")
        if has_vietnamese(f"{s.get('say', '')} {s.get('use', '')}"):
            errors.append(f"{uid}: lesson sentence {i} say and use must be in English (use_vi is the translation)")
        if "..." in s.get("say", ""):
            errors.append(f"{uid}: lesson sentence {i} must be a full sentence, not a template")
        if not (isinstance(s.get("phrase"), int) and 0 <= s["phrase"] < n):
            errors.append(f"{uid}: lesson sentence {i} points to a missing phrase")
    return errors


def public(unit: dict) -> dict:
    """What the lesson page needs: the unit, its vocabulary and sentences, and every teacher line."""
    lesson = unit["lesson"]
    return {
        "id": unit["id"],
        "title": unit["title"],
        "goal": unit["goal"],
        "partner": unit.get("partner", "Người phỏng vấn"),
        "vocab": lesson["vocab"],
        "sentences": [{"say": s["say"], "use": s["use"], "use_vi": s["use_vi"]} for s in lesson["sentences"]],
        "lines": lines(unit),
    }
