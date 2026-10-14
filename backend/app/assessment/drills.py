"""Pronunciation drills: read sentences aimed at one sound you get wrong, compared word by word.

Each sentence lists its focus words (the ones carrying the sound), which are scored on their own.
A personal set is built from your history: sentences whose latest reading had a misheard word.
No LLM is involved (docs/features/pronunciation-drills.md).
"""

from __future__ import annotations

import hashlib
import json

from app.core.config import DATA_DIR
from app.utils.compare import compare, word_tokens

MINE = "mine"  # id of the personal set
MINE_LIMIT = 12  # sentences in the personal set, newest first
WINDOW = 20  # recent attempts used for accuracy (the stage 1 gate uses the same window)

sets: list[dict] = json.loads((DATA_DIR / "drills.json").read_text(encoding="utf-8"))


def sentence_id(text: str) -> str:
    """Stable id from the text, so a personal sentence keeps its id while the list changes."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


for _s in sets:
    for _x in _s["sentences"]:
        _x["id"] = sentence_id(_x["text"])
sets_by_id: dict[str, dict] = {s["id"]: s for s in sets}


def _key(word: str) -> str:
    return " ".join(word_tokens(word))


def validate(drill_sets: list[dict]) -> list[str]:
    """Problems in the drill data; an empty list means it is usable."""
    errors: list[str] = []
    seen: set[str] = set()
    for s in drill_sets:
        sid = s.get("id", "?")
        if sid in seen or sid == MINE:
            errors.append(f"{sid}: duplicate or reserved id")
        seen.add(sid)
        for key in ("title", "tip", "sentences"):
            if not s.get(key):
                errors.append(f"{sid}: missing {key}")
        for x in s.get("sentences", []):
            words = {_key(w) for w in x.get("text", "").split()}
            if not x.get("focus"):
                errors.append(f"{sid}: {x.get('text')!r} has no focus words")
            for f in x.get("focus", []):
                if _key(f) not in words:
                    errors.append(f"{sid}: focus {f!r} is not a word of {x.get('text')!r}")
    return errors


_errors = validate(sets)
if _errors:
    raise ValueError("Invalid drills.json:\n" + "\n".join(_errors))


def score(target: str, focus: list[str], heard: str) -> dict:
    """compare() of the reading, with focus words marked and counted separately."""
    result = compare(target, heard)
    keys = {_key(f) for f in focus}
    hit = total = 0
    for item in result["items"]:
        if item["kind"] == "word" and _key(item["text"]) in keys:
            item["focus"] = True
            total += 1
            hit += item["status"] == "ok"
    return {**result, "focus_correct": hit, "focus_total": total}


def best_reading(text: str, focus: list[str], attempts: list[dict]) -> dict | None:
    """The best drill reading of `text` (from any set), scored with these focus words.

    Best = most focus words right, then most words right; on a tie the latest wins. `attempts` are drill
    rows oldest first. Returns score() plus heard, created_at, audio and attempts (readings of this text),
    or None before the first reading.
    """
    best: dict | None = None
    rank: tuple[float, float] | None = None
    n = 0
    for a in attempts:
        if a["target"] != text:
            continue
        n += 1
        r = score(text, focus, a["heard"])
        k = (r["focus_correct"] / r["focus_total"] if r["focus_total"] else 1.0, r["accuracy"])
        if rank is None or k >= rank:
            rank = k
            best = {**r, "heard": a["heard"], "created_at": a["created_at"], "audio": a.get("audio")}
    return {**best, "attempts": n} if best else None


def misheard_words(target: str, heard: str) -> list[str]:
    """Written words of `target` that were not heard correctly, without punctuation."""
    out: list[str] = []
    for item in compare(target, heard)["items"]:
        word = item["text"].strip(".,!?;:\"'()")
        if item["kind"] == "word" and item["status"] != "ok" and word and word not in out:
            out.append(word)
    return out


def personal_sentences(attempts: list[dict]) -> list[dict]:
    """Sentences whose latest reading had a mistake, newest first; focus = the words misheard then.

    `attempts` (oldest first) are readings from shadowing and drills: {target, heard, correct, total}.
    Reading a sentence without mistakes drops it from the set.
    """
    latest: dict[str, tuple[int, dict]] = {}
    for i, a in enumerate(attempts):
        latest[a["target"]] = (i, a)
    out: list[dict] = []
    for _i, a in sorted(latest.values(), key=lambda v: v[0], reverse=True):
        if a["correct"] < a["total"]:
            text = a["target"]
            out.append({"id": sentence_id(text), "text": text, "focus": misheard_words(text, a["heard"])})
    return out[:MINE_LIMIT]


def focus_accuracy(attempts: list[dict], window: int = WINDOW) -> dict:
    """Focus words read correctly over the last `window` drill attempts: {attempts, accuracy %}."""
    recent = attempts[-window:]
    total = sum(a["focus_total"] for a in recent)
    hit = sum(a["focus_correct"] for a in recent)
    return {"attempts": len(recent), "accuracy": round(hit / total * 100) if total else None}
