from __future__ import annotations

import json
import logging
import re
from typing import TypedDict

from app.services.lm_client import LMStudioClient

log = logging.getLogger(__name__)

_SCORE_KEYS = ("fluency", "vocabulary", "grammar")
_MIN_SCORE = 0.0
_MAX_SCORE = 10.0
_DEFAULT_GRAMMAR = 6.0
_TTR_MULTIPLIER = 12

# (wpm_threshold, score) -- evaluated low-to-high; first match wins
_WPM_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (30, 2.0),
    (60, 4.5),
    (100, 6.5),
    (130, 8.0),
)
_WPM_CEILING_SCORE = 9.0
_MIN_WORDS_FOR_FLUENCY = 5
_MIN_WORDS_FOR_VOCAB = 6
_SHORT_UTTERANCE_FLUENCY = 4.0
_SHORT_UTTERANCE_VOCAB = 5.5

_MAX_FEEDBACK_LENGTH = 500
_EMPTY_TRANSCRIPT_FEEDBACK = (
    "It looks like the recording was empty — try again and speak clearly into the mic!"
)

_FALLBACK_FEEDBACK = (
    "Good attempt! Keep practicing—try to speak a bit more smoothly "
    "and check the grammar of your main verb. You're making progress."
)

_SCORING_PROMPT = """You are a friendly English tutor giving feedback on a learner's spoken response.

Topic: {topic}
Learner's speech (transcribed): {transcript}
Duration (seconds): {duration:.1f}

If the transcript is in Vietnamese or mostly not English:
- Set vocabulary <= 3.0 and grammar <= 3.0.
- Set fluency based on length only (short = low).
- Set overall as the average of the scores.
- In "feedback", kindly encourage them to try again in English (e.g. "That sounded like Vietnamese—give it a go in English next time, even a short sentence helps!").

Otherwise, score each dimension from 0 to 10:

- fluency: Based on smoothness and pacing. Very short answers or many pauses = low; natural, steady speech = high.
- vocabulary: Range and appropriateness of words (basic vs varied and precise).
- grammar: Grammatical correctness and sentence structure.

- overall: MUST be the average of fluency, vocabulary, and grammar (rounded to 1 decimal).

Write "feedback" in 2–4 short sentences:
- First: one specific thing they did well.
- Second: one clear, actionable improvement.
- Third (if needed): suggest a natural correction (e.g. "You could say: ...").

Keep the tone encouraging, natural, and concise. Avoid generic comments like "improve your grammar".

Respond ONLY with valid JSON in exactly this format (no extra text, no markdown):
{{"fluency": 7.0, "vocabulary": 6.5, "grammar": 8.0, "overall": 7.2, "feedback": "Your 2-4 sentences here."}}
"""

_SESSION_FEEDBACK_PROMPT = """Bạn là giáo viên tiếng Anh. Học viên vừa kết thúc một phiên luyện nói.

Chủ đề / ngữ cảnh: {topic}

Các lượt (học viên nói → gia sư trả lời), theo thứ tự:
{turns_block}

Điểm trung bình cả phiên (thang 10):
- Speaking / độ trôi chảy: {flu:.1f}
- Từ vựng: {voc:.1f}
- Ngữ pháp: {gram:.1f}
- Tổng thể: {ov:.1f}

Viết MỘT tin nhắn duy nhất bằng tiếng Việt (giọng thân thiện), gồm:
1) Một đoạn ngắn nêu lại điểm trung bình cả phiên (thang 10) cho: speaking/độ trôi chảy, từ vựng, ngữ pháp, tổng thể — dùng đúng các số đã cho ở trên (có thể gạch đầu dòng).
2) Phần nhận xét: điểm mạnh/yếu nổi bật qua các lượt; chỉ ra lỗi sai cụ thể nếu có (ngữ pháp, từ vựng, cách nói).
3) Gợi ý cách cải thiện rõ ràng theo từng mặt (nói, từ vựng, ngữ pháp) tùy mức điểm.
4) Kết: một câu động viên.

Không dùng markdown, không dùng JSON, không lặp lại toàn bộ hội thoại. Tối đa ~280 từ.
"""


def _trunc_text(text: str, max_len: int) -> str:
    t = text.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


class ScoreResult(TypedDict):
    fluency: float
    vocabulary: float
    grammar: float
    overall: float
    feedback: str


def _clamp(value: float) -> float:
    return max(_MIN_SCORE, min(_MAX_SCORE, value))


def _compute_overall(fluency: float, vocabulary: float, grammar: float) -> float:
    return round((fluency + vocabulary + grammar) / 3, 1)


class ScoringService:
    def __init__(self, lm: LMStudioClient) -> None:
        self._lm = lm

    @staticmethod
    def _fluency_heuristic(transcript: str, duration_seconds: float) -> float:
        """Quick fluency estimate based on words-per-minute."""
        words = len(transcript.split())
        if words < _MIN_WORDS_FOR_FLUENCY:
            return _SHORT_UTTERANCE_FLUENCY
        if duration_seconds <= 0:
            return 5.0
        wpm = (words / duration_seconds) * 60
        for threshold, score in _WPM_THRESHOLDS:
            if wpm < threshold:
                return score
        return _WPM_CEILING_SCORE

    @staticmethod
    def _vocab_heuristic(transcript: str) -> float:
        """Type-token ratio as quick vocabulary variety estimate."""
        words = re.findall(r"\b[a-z]+\b", transcript.lower())
        if not words:
            return 5.0
        if len(words) < _MIN_WORDS_FOR_VOCAB:
            return _SHORT_UTTERANCE_VOCAB
        ttr = len(set(words)) / len(words)
        return min(_MAX_SCORE, round(ttr * _TTR_MULTIPLIER, 1))

    @staticmethod
    def _parse_lm_response(raw: str) -> ScoreResult | None:
        """Extract and validate the JSON score object from raw LM output."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```\s*$", "", text)

        start = text.find("{")
        if start == -1:
            log.warning("No JSON object found in LM response")
            return None

        try:
            data, _end = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError as exc:
            log.warning("Invalid JSON in LM response: %s", exc)
            return None

        if not isinstance(data, dict):
            log.warning("LM response JSON was not an object")
            return None

        missing = [k for k in (*_SCORE_KEYS, "feedback") if k not in data]
        if missing:
            log.warning("LM response missing keys: %s", missing)
            return None

        try:
            for key in _SCORE_KEYS:
                data[key] = _clamp(float(data[key]))
        except (TypeError, ValueError) as exc:
            log.warning("Non-numeric score value: %s", exc)
            return None

        data["overall"] = _compute_overall(
            data["fluency"], data["vocabulary"], data["grammar"]
        )
        data["feedback"] = str(data["feedback"])[:_MAX_FEEDBACK_LENGTH]
        return ScoreResult(**{k: data[k] for k in ScoreResult.__annotations__})

    async def score(
        self,
        transcript: str,
        topic: str,
        duration_seconds: float = 0.0,
    ) -> ScoreResult:
        """Return scoring dict with keys: fluency, vocabulary, grammar, overall, feedback."""
        stripped = transcript.strip()
        if not stripped:
            return ScoreResult(
                fluency=0.0,
                vocabulary=0.0,
                grammar=0.0,
                overall=0.0,
                feedback=_EMPTY_TRANSCRIPT_FEEDBACK,
            )

        safe_transcript = stripped.replace("{", "{{").replace("}", "}}")
        safe_topic = topic.replace("{", "{{").replace("}", "}}")

        messages = [
            {
                "role": "user",
                "content": _SCORING_PROMPT.format(
                    topic=safe_topic,
                    transcript=safe_transcript,
                    duration=duration_seconds,
                ),
            }
        ]
        try:
            raw = await self._lm.generate_text(
                messages, temperature=0.2, max_tokens=320
            )
            result = self._parse_lm_response(raw)
            if result is not None:
                return result
        except Exception:
            log.exception("LM scoring failed, falling back to heuristics")

        fluency = self._fluency_heuristic(stripped, duration_seconds)
        vocab = self._vocab_heuristic(stripped)
        return ScoreResult(
            fluency=fluency,
            vocabulary=vocab,
            grammar=_DEFAULT_GRAMMAR,
            overall=_compute_overall(fluency, vocab, _DEFAULT_GRAMMAR),
            feedback=_FALLBACK_FEEDBACK,
        )

    def _fallback_session_feedback_vi(self, averages: dict[str, float]) -> str:
        return (
            "📊 Điểm trung bình phiên (thang 10)\n"
            f"• Speaking (độ trôi chảy): {averages['fluency']:.1f}\n"
            f"• Từ vựng: {averages['vocabulary']:.1f}\n"
            f"• Ngữ pháp: {averages['grammar']:.1f}\n"
            f"• Tổng thể: {averages['overall']:.1f}\n\n"
            "Hãy xem lại các câu bạn đã nói: thử nối ý bằng because / so / but, "
            "dùng đúng thì động từ với chủ ngữ, và mở rộng từ vựng theo chủ đề. "
            "Luyện nói thêm từng câu hoàn chỉnh — bạn đang tiến bộ!"
        )

    async def session_feedback_message(
        self,
        topic: str,
        turn_pairs: list[tuple[str, str]],
        averages: dict[str, float],
    ) -> str:
        """
        One tutor-style recap for the whole session (Vietnamese), using scores + full dialogue.
        """
        if not turn_pairs or not averages:
            return ""

        parts: list[str] = []
        for i, (user_t, asst_t) in enumerate(turn_pairs, 1):
            uu = _trunc_text(user_t, 480)
            aa = _trunc_text(asst_t, 480)
            parts.append(f"Lượt {i} — Học viên: {uu}\nGia sư: {aa}")
        turns_block = "\n\n".join(parts)

        safe_topic = topic.replace("{", "{{").replace("}", "}}")
        safe_block = turns_block.replace("{", "{{").replace("}", "}}")
        flu = float(averages["fluency"])
        voc = float(averages["vocabulary"])
        gram = float(averages["grammar"])
        ov = float(averages["overall"])

        user_msg = _SESSION_FEEDBACK_PROMPT.format(
            topic=safe_topic,
            turns_block=safe_block,
            flu=flu,
            voc=voc,
            gram=gram,
            ov=ov,
        )
        messages = [{"role": "user", "content": user_msg}]
        try:
            raw = await self._lm.generate_text(
                messages, temperature=0.35, max_tokens=720
            )
            text = raw.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:\w*)?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```\s*$", "", text)
            if len(text) > 20:
                return text[:2800]
        except Exception:
            log.exception("Session feedback LM failed; using fallback text")

        return self._fallback_session_feedback_vi(averages)
