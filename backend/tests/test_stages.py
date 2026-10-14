from app.assessment import drills
from app.assessment.fluency import group_runs
from app.assessment.stages import check_meets, evaluate, stages, validate
from app.interview.units import topics

LEVEL = {"seconds": 90, "wpm_speaking": 95, "hesitations_per_100": 5}


def check(duration, wpm, hes, not_english=False):
    return {"created_at": "2026-10-11T10:00:00", "duration_s": duration, "wpm_speaking": wpm,
            "hesitations_per_100": hes, "not_english": not_english}  # fmt: skip


def evidence(**kw):
    base = {
        "completed": set(),
        "topic_units": {"daily": ["d1", "d2"], "workplace": ["w1"], "intro": ["i1"], "technical": [],
                        "behavioral": [], "closing": []},  # fmt: skip
        "drill_attempts": [],
        "drill_set_ids": [s["id"] for s in drills.sets],
        "checks": [],
        "fluency_runs": 0,
    }
    return {**base, **kw}


def good_drills():
    return [{"set_id": s["id"], "focus_correct": 2, "focus_total": 2} for s in drills.sets] * 4


def status(ev):
    return [s["status"] for s in evaluate(stages, ev)]


def test_stage_data_is_valid_and_covers_every_topic():
    assert validate(stages, [t["id"] for t in topics]) == []
    assert validate(stages, [t["id"] for t in topics] + ["new-topic"])  # a topic outside every stage


def test_check_levels():
    assert check_meets(check(100, 100, 4.0), LEVEL)
    assert not check_meets(check(100, 100, 5.0), LEVEL)  # must stay below
    assert not check_meets(check(80, 120, 1.0), LEVEL)
    assert not check_meets(check(100, None, None), LEVEL)  # not measurable
    assert not check_meets(check(100, 100, 1.0, not_english=True), LEVEL)


def test_only_the_first_stage_is_open_at_the_start():
    assert status(evidence()) == ["current", "locked", "locked", "locked", "locked"]


def test_the_sounds_stage_passes_once_every_set_is_practised():
    some = [{"set_id": s["id"], "focus_correct": 1, "focus_total": 1} for s in drills.sets[:-1]]
    assert status(evidence(drill_attempts=some))[0] == "current"
    # accuracy is not part of this gate: Whisper misjudges focus words too often (docs/features/roadmap.md)
    poor = [{"set_id": s["id"], "focus_correct": 0, "focus_total": 2} for s in drills.sets]
    assert status(evidence(drill_attempts=poor))[:2] == ["passed", "current"]


def test_a_drill_accuracy_gate_needs_enough_attempts_and_accuracy():
    gated = [{**stages[0], "gate": {"drill_accuracy": 90}}]
    few = [{"set_id": s["id"], "focus_correct": 1, "focus_total": 1} for s in drills.sets]  # 5 < window
    assert [s["status"] for s in evaluate(gated, evidence(drill_attempts=few))] == ["current"]
    poor = [{**a, "focus_correct": 1, "focus_total": 2} for a in good_drills()]
    assert [s["status"] for s in evaluate(gated, evidence(drill_attempts=poor))] == ["current"]
    assert [s["status"] for s in evaluate(gated, evidence(drill_attempts=good_drills()))] == ["passed"]


def test_a_stage_needs_its_units_and_its_check_level():
    ev = evidence(drill_attempts=good_drills(), completed={"d1", "d2"})
    assert status(ev)[1] == "current"  # no check yet
    ev["checks"] = [check(65, 85, 6.0)]
    assert status(ev)[:3] == ["passed", "passed", "current"]


def test_an_early_strong_check_does_not_skip_a_locked_stage():
    ev = evidence(checks=[check(130, 120, 1.0)], completed={"d1", "d2", "w1", "i1"}, fluency_runs=2)
    assert status(ev) == ["current", "locked", "locked", "locked", "locked"]


def test_group_runs_keeps_the_latest_try_of_each_round():
    rows = [
        {"run": "a", "round": 1, "prompt_id": "p", "prompt": "P", "created_at": "1", "words": 10},
        {"run": "a", "round": 2, "prompt_id": "p", "prompt": "P", "created_at": "2", "words": 20},
        {"run": "a", "round": 2, "prompt_id": "p", "prompt": "P", "created_at": "3", "words": 30},
        {"run": "a", "round": 3, "prompt_id": "p", "prompt": "P", "created_at": "4", "words": 40},
        {"run": "b", "round": 1, "prompt_id": "q", "prompt": "Q", "created_at": "5", "words": 50},
    ]
    a, b = group_runs(rows)
    assert a["complete"] and [r["words"] for r in a["rounds"]] == [10, 30, 40]
    assert not b["complete"]
