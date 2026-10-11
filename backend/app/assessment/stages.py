"""Roadmap stages, unlocked one after another by measured results (docs/features/roadmap.md).

A stage is passed when every requirement of its gate is met; the next stage opens only then.
Requirements are objective: units completed, pronunciation drill accuracy, 4/3/2 exercises done,
and a speaking check reaching that stage's level. The check levels rise stage by stage from the
placement result, up to the check's own targets.
"""

from __future__ import annotations

import json

from app.assessment import drills
from app.core.config import DATA_DIR

stages: list[dict] = json.loads((DATA_DIR / "stages.json").read_text(encoding="utf-8"))

GATE_KEYS = {"drill_sets", "drill_accuracy", "check", "fluency_runs"}
CHECK_KEYS = {"seconds", "wpm_speaking", "hesitations_per_100"}


def validate(stage_list: list[dict], topic_ids: list[str]) -> list[str]:
    """Problems in the stage data; every topic must belong to exactly one stage."""
    errors: list[str] = []
    owner: dict[str, str] = {}
    for s in stage_list:
        sid = s.get("id", "?")
        for key in ("title", "goal"):
            if not s.get(key):
                errors.append(f"{sid}: missing {key}")
        if not (s.get("topics") or s.get("practice")):
            errors.append(f"{sid}: needs topics or practice")
        if s.get("practice") not in (None, "drills", "fluency"):
            errors.append(f"{sid}: unknown practice {s['practice']!r}")
        if unknown := set(s.get("gate", {})) - GATE_KEYS:
            errors.append(f"{sid}: unknown gate keys {sorted(unknown)}")
        if unknown := set(s.get("gate", {}).get("check", {})) - CHECK_KEYS:
            errors.append(f"{sid}: unknown check keys {sorted(unknown)}")
        for t in s.get("topics", []):
            if t not in topic_ids:
                errors.append(f"{sid}: unknown topic {t!r}")
            elif t in owner:
                errors.append(f"{sid}: topic {t!r} is already in stage {owner[t]!r}")
            owner[t] = sid
    for t in topic_ids:
        if t not in owner:
            errors.append(f"topic {t!r} is in no stage")
    return errors


def check_meets(c: dict, level: dict) -> bool:
    """Whether one speaking check reaches a stage level ({seconds, wpm_speaking, hesitations_per_100})."""
    if c["not_english"] or c["duration_s"] < level.get("seconds", 0):
        return False
    if "wpm_speaking" in level and (c["wpm_speaking"] or 0) < level["wpm_speaking"]:
        return False
    if "hesitations_per_100" in level:
        h = c["hesitations_per_100"]
        if h is None or h >= level["hesitations_per_100"]:
            return False
    return True


def requirements(stage: dict, evidence: dict) -> list[dict]:
    """What the stage asks for and how far the learner is. `evidence` holds:
    completed (unit ids), topic_units ({topic: [unit ids]}), drill_attempts (oldest first),
    drill_set_ids (built-in sets), checks (oldest first), fluency_runs (complete exercises)."""
    gate = stage.get("gate", {})
    out: list[dict] = []
    if stage.get("topics"):
        ids = [u for t in stage["topics"] for u in evidence["topic_units"].get(t, [])]
        done = sum(u in evidence["completed"] for u in ids)
        out.append({"kind": "units", "done": done, "total": len(ids), "met": done == len(ids)})
    if gate.get("drill_sets"):
        practised = {a["set_id"] for a in evidence["drill_attempts"]}
        sets = evidence["drill_set_ids"]
        done = sum(s in practised for s in sets)
        out.append({"kind": "drill_sets", "done": done, "total": len(sets), "met": done == len(sets)})
    if "drill_accuracy" in gate:
        recent = drills.focus_accuracy(evidence["drill_attempts"])
        met = recent["attempts"] >= drills.WINDOW and (recent["accuracy"] or 0) >= gate["drill_accuracy"]
        out.append({"kind": "drill_accuracy", "target": gate["drill_accuracy"], "window": drills.WINDOW,
                    **recent, "met": met})  # fmt: skip
    if "fluency_runs" in gate:
        done = min(evidence["fluency_runs"], gate["fluency_runs"])
        out.append({"kind": "fluency_runs", "done": done, "total": gate["fluency_runs"],
                    "met": done == gate["fluency_runs"]})  # fmt: skip
    if "check" in gate:
        level = gate["check"]
        passing = [c for c in evidence["checks"] if check_meets(c, level)]
        shown = (passing or evidence["checks"] or [None])[-1]
        best = shown and {k: shown[k] for k in ("created_at", "duration_s", "wpm_speaking", "hesitations_per_100")}
        out.append({"kind": "check", "target": level, "latest": best, "met": bool(passing)})
    return out


def evaluate(stage_list: list[dict], evidence: dict) -> list[dict]:
    """Stages with status: passed, current (open, gate not met yet) or locked."""
    out: list[dict] = []
    open_ = True
    for s in stage_list:
        reqs = requirements(s, evidence)
        met = all(r["met"] for r in reqs)
        status = "locked" if not open_ else "passed" if met else "current"
        out.append({**s, "requirements": reqs, "status": status})
        open_ = status == "passed"
    return out


def open_topics(report_: list[dict]) -> set[str]:
    """Topics of the stages that are open (passed or current)."""
    return {t for s in report_ if s["status"] != "locked" for t in s.get("topics", [])}
