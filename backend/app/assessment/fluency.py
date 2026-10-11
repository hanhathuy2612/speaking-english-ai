"""4/3/2 fluency exercise: tell the same story three times in 4, 3 and 2 minutes.

Repeating the content with less time pushes speed up and hesitation down, because the words
are already found. Each round is measured like the speaking check (docs/features/fluency-432.md).
Prompts are separate from the check's, so the check stays on topics you have not practised.
"""

from __future__ import annotations

import json
import random

from app.assessment.metrics import pick_least_used
from app.core.config import DATA_DIR

ROUNDS = [240, 180, 120]  # seconds allowed in rounds 1, 2, 3

prompts: list[dict] = json.loads((DATA_DIR / "fluency_prompts.json").read_text(encoding="utf-8"))
prompts_by_id: dict[str, dict] = {p["id"]: p for p in prompts}


def pick_prompt(used_counts: dict[str, int], exclude: str | None = None, rng=random) -> dict:
    return pick_least_used(prompts, used_counts, exclude, rng)


def group_runs(rounds: list[dict]) -> list[dict]:
    """Rounds (oldest first) grouped into exercises: [{run, prompt_id, prompt, created_at, rounds,
    complete}], oldest first. A retried round replaces the earlier one."""
    runs: dict[str, dict] = {}
    for r in rounds:
        run = runs.setdefault(
            r["run"],
            {"run": r["run"], "prompt_id": r["prompt_id"], "prompt": r["prompt"],
             "created_at": r["created_at"], "rounds": {}},
        )  # fmt: skip
        run["rounds"][r["round"]] = r
    out = []
    for run in runs.values():
        done = [run["rounds"][k] for k in sorted(run["rounds"])]
        out.append({**run, "rounds": done, "complete": len(done) == len(ROUNDS)})
    return out
