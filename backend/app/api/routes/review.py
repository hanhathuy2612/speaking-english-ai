"""Review cards API (docs/features/review.md): spaced review of past corrections, no LLM."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.config import STT_VOCAB
from app.interview import review
from app.interview.units import units_by_id
from app.services import history, stt, tts

router = APIRouter(prefix="/api/review", tags=["review"])

ROUND = 15  # cards per daily round, about five minutes


def _card(c: dict) -> dict:
    unit = units_by_id.get(c["unit_id"])
    return {
        "id": c["id"], "kind": c["kind"], "unit_id": c["unit_id"],
        "unit_title": unit["title"] if unit else c["unit_id"],
        "question": c["question"], "said": c["said"], "target": c["target"],
        "box": c["box"], "due": c["due"], "reviews": c["reviews"], "session_id": c["session_id"],
    }  # fmt: skip


def _stats(today: date) -> dict:
    s = history.card_stats(today.isoformat(), (today - timedelta(days=30)).isoformat(), review.LEARNED_BOX)
    return {**s, "recall": round(s["good"] / s["reviews"] * 100) if s["reviews"] else None}


@router.get("")
async def review_state(session: int | None = None) -> dict:
    """Cards to review: all cards of one session (`?session=`, end-of-session review),
    otherwise the cards due today, at most one round."""
    today = date.today()
    review.sync(today)
    if session is not None:
        cards = history.list_cards(session_id=session)
    else:
        cards = history.list_cards(due_by=today.isoformat())[:ROUND]
    return {"enabled": history.enabled(), "stats": _stats(today), "cards": [_card(c) for c in cards]}


@router.get("/count")
async def review_count() -> dict:
    """Cards due today, for the badge in the navigation."""
    today = date.today()
    review.sync(today)
    return {"due": history.card_stats(today.isoformat(), today.isoformat())["due"]}


def _get(card_id: int) -> dict:
    card = history.get_card(card_id)
    if not card:
        raise HTTPException(404)
    return card


@router.get("/{card_id}/audio")
async def review_audio(card_id: int) -> Response:
    """The NOTE (or the phrase) read aloud."""
    card = _get(card_id)
    return Response(await tts.cached_tts(card["target"]), media_type="audio/mpeg")


@router.post("/{card_id}/attempt")
async def review_attempt(card_id: int, request: Request) -> dict:
    """Transcribe one spoken attempt and run the objective checks. Nothing is stored here:
    the learner's grade (POST .../grade) is what moves the card."""
    card = _get(card_id)
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
async def review_grade(card_id: int, grade: Grade) -> dict:
    card = _get(card_id)
    box, due = review.schedule(card["box"], grade.result, date.today())
    history.grade_card(card_id, box, due.isoformat(), grade.result, grade.model_dump(exclude={"result"}))
    return {"box": box, "due": due.isoformat()}


@router.post("/{card_id}/suspend")
async def review_suspend(card_id: int) -> dict:
    """Drop a card for good (for example a NOTE that is not worth learning)."""
    _get(card_id)
    history.suspend_card(card_id)
    return {"ok": True}
