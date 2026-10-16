"""Review cards API (docs/features/review.md): spaced review of past corrections, no LLM."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import current_user
from app.core.config import STT_VOCAB
from app.interview import review
from app.interview.units import units_by_id
from app.services import history, stt, tts

router = APIRouter(prefix="/api/review", tags=["review"])

ROUND = 15  # cards per daily round, about five minutes


def _source(unit_id: str) -> str:
    """What the card came from, for its label: a unit, or a speaking check ('check:<prompt id>')."""
    if unit_id.startswith("check:"):
        return "Kiểm tra nói"
    unit = units_by_id.get(unit_id)
    return unit["title"] if unit else unit_id


def _card(c: dict) -> dict:
    return {
        "id": c["id"], "kind": c["kind"], "unit_id": c["unit_id"],
        "unit_title": _source(c["unit_id"]),
        "question": c["question"], "said": c["said"], "target": c["target"],
        "box": c["box"], "due": c["due"], "reviews": c["reviews"], "session_id": c["session_id"],
    }  # fmt: skip


def _stats(uid: int, today: date) -> dict:
    s = history.card_stats(uid, today.isoformat(), (today - timedelta(days=30)).isoformat(), review.LEARNED_BOX)
    return {**s, "recall": round(s["good"] / s["reviews"] * 100) if s["reviews"] else None}


@router.get("")
def review_state(session: int | None = None, user: dict = Depends(current_user)) -> dict:
    """Cards to review: all cards of one session (`?session=`, end-of-session review),
    otherwise the cards due today, at most one round."""
    today, uid = date.today(), user["id"]
    review.sync(uid, today)
    if session is not None:
        cards = history.list_cards(uid, session_id=session)
    else:
        cards = history.list_cards(uid, due_by=today.isoformat())[:ROUND]
    return {"enabled": history.enabled(), "stats": _stats(uid, today), "cards": [_card(c) for c in cards]}


@router.get("/count")
def review_count(user: dict = Depends(current_user)) -> dict:
    """Cards due today, for the badge in the navigation."""
    today = date.today()
    review.sync(user["id"], today)
    return {"due": history.card_stats(user["id"], today.isoformat(), today.isoformat())["due"]}


def _get(card_id: int, user: dict = Depends(current_user)) -> dict:
    """The card in the path, when it is the user's (a route dependency)."""
    card = history.get_card(user["id"], card_id)
    if not card:
        raise HTTPException(404)
    return card


@router.get("/{card_id}/audio")
async def review_audio(card: dict = Depends(_get)) -> Response:
    """The NOTE (or the phrase) read aloud."""
    return Response(await tts.cached_tts(card["target"]), media_type="audio/mpeg")


@router.post("/{card_id}/attempt")
async def review_attempt(request: Request, card: dict = Depends(_get)) -> dict:
    """Transcribe one spoken attempt and run the objective checks. Nothing is stored here:
    the learner's grade (POST .../grade) is what moves the card."""
    path = stt.save_recording(await request.body())
    try:
        result = await asyncio.to_thread(stt.transcribe, path, STT_VOCAB)
    finally:
        stt.finish_recording(path, None)
    return review.check_attempt(card, result["text"])


class Grade(BaseModel):
    result: Literal["good", "again"]
    heard: str | None = None
    correct: int | None = None
    total: int | None = None


@router.post("/{card_id}/grade")
def review_grade(grade: Grade, card: dict = Depends(_get)) -> dict:
    box, due = review.schedule(card["box"], grade.result, date.today())
    history.grade_card(card["id"], box, due.isoformat(), grade.result, grade.model_dump(exclude={"result"}))
    return {"box": box, "due": due.isoformat()}


@router.post("/{card_id}/suspend")
def review_suspend(card: dict = Depends(_get)) -> dict:
    """Drop a card for good (for example a NOTE that is not worth learning)."""
    history.suspend_card(card["id"])
    return {"ok": True}
