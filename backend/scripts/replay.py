"""Replay typed answers (skipping STT) against a running server to compare prompts before/after.

Run from backend/ (the server must be running; agents test on port 8001):
  python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws

answers.txt: one answer per line, in the order of a real session.
Prints each turn: your answer, the interviewer's reply, NOTE and the RETRY flag.
Check by eye: does the AI speak in the first person like the candidate, repeat old questions,
or fail to cover all questions?
"""

from __future__ import annotations

import argparse
import asyncio
import json

import websockets


async def run_once(url: str, unit: str, answers: list[str]) -> None:
    async with websockets.connect(url, max_size=None) as ws:

        async def until_done(show: bool) -> None:
            said: list[str] = []
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    continue
                m = json.loads(msg)
                if m["type"] == "sentence" and m["role"] == "ai":
                    said.append(m["text"])
                elif m["type"] == "note" and show:
                    print(f"   AI:   {' '.join(said)}")
                    print(f"   NOTE: {m['text']}  {'(RETRY)' if m['retry'] else ''}")
                    for st in m.get("steps", []):
                        print(f"         {'[x]' if st['done'] else '[ ]'} {st['say']}")
                elif m["type"] == "progress" and show:
                    where = "done" if m["done"] else f"question {m['q']}/{m['n']}"
                    print(f"   [{where}]")
                elif m["type"] == "error":
                    print(f"   ERROR: {m['msg']}")
                elif m["type"] == "turn_done":
                    if not show:
                        print(f"   AI:   {' '.join(said)}")
                    return

        await ws.send(json.dumps({"type": "start", "unit": unit}))
        await until_done(show=False)
        for i, answer in enumerate(answers, 1):
            print(f"{i:>2}. YOU:  {answer}")
            await ws.send(json.dumps({"type": "text", "text": answer}))
            await until_done(show=True)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("answers")
    ap.add_argument("--unit", default="tell-me-about-yourself")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--url", default="ws://localhost:8000/ws")
    args = ap.parse_args()
    with open(args.answers, encoding="utf-8") as f:
        answers = [line.strip() for line in f if line.strip()]
    for r in range(1, args.runs + 1):
        print(f"\n===== Run {r}/{args.runs} =====")
        await run_once(args.url, args.unit, answers)


if __name__ == "__main__":
    asyncio.run(main())
