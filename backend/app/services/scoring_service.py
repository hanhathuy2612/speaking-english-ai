import json
import re
import time

from app.services.lm_client import LMStudioClient

_SCORING_PROMPT = """You are an English language evaluator. Evaluate the following learner's spoken response.

Topic: {topic}
Learner's speech (transcribed): {transcript}
Duration (seconds): {duration:.1f}

Score each dimension from 0 to 10:
- fluency: How smoothly and quickly they spoke (estimate from word count vs duration).
- vocabulary: Range and accuracy of vocabulary.
- grammar: Grammatical correctness.
- overall: Holistic score.
Also provide a short constructive feedback in 1-2 sentences.

Respond ONLY with valid JSON in exactly this format:
{{"fluency": 7.0, "vocabulary": 6.5, "grammar": 8.0, "overall": 7.2, "feedback": "Your sentence."}}"""


class ScoringService:
    def __init__(self, lm: LMStudioClient) -> None:
        self._lm = lm

    def _fluency_heuristic(self, transcript: str, duration_seconds: float) -> float:
        """Quick fluency estimate based on words-per-minute."""
        words = len(transcript.split())
        if duration_seconds <= 0:
            return 5.0
        wpm = (words / duration_seconds) * 60
        # Native-level ≈ 130-160 wpm; learner target ~80-120 wpm
        if wpm < 30:
            return 2.0
        if wpm < 60:
            return 4.5
        if wpm < 100:
            return 6.5
        if wpm < 130:
            return 8.0
        return 9.0

    def _vocab_heuristic(self, transcript: str) -> float:
        """Type-token ratio as quick vocabulary variety estimate."""
        words = re.findall(r"\b[a-z]+\b", transcript.lower())
        if not words:
            return 5.0
        ttr = len(set(words)) / len(words)
        return min(10.0, round(ttr * 12, 1))

    async def score(
        self,
        transcript: str,
        topic: str,
        duration_seconds: float = 0.0,
    ) -> dict:
        """Return scoring dict with keys: fluency, vocabulary, grammar, overall, feedback."""
        messages = [
            {
                "role": "user",
                "content": _SCORING_PROMPT.format(
                    topic=topic,
                    transcript=transcript,
                    duration=duration_seconds,
                ),
            }
        ]
        try:
            raw = await self._lm.generate_text(
                messages, temperature=0.1, max_tokens=200
            )
            # Extract JSON from response
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass

        # Fallback to heuristic scoring if LM fails
        fluency = self._fluency_heuristic(transcript, duration_seconds)
        vocab = self._vocab_heuristic(transcript)
        overall = round((fluency + vocab + 6.0) / 3, 1)
        return {
            "fluency": fluency,
            "vocabulary": vocab,
            "grammar": 6.0,
            "overall": overall,
            "feedback": "Keep practicing! Focus on speaking more smoothly.",
        }
