"""Phát lại các câu trả lời (gõ chữ, bỏ qua STT) qua server đang chạy để so prompt trước/sau.

Chạy (server phải đang chạy ở cổng 8000):
  python replay.py answers.txt --unit tell-me-about-yourself --runs 3

answers.txt: mỗi dòng một câu trả lời, theo đúng thứ tự trong phiên thật.
In ra từng lượt: câu bạn nói, lời người phỏng vấn, NOTE, và cờ RETRY.
Dò bằng mắt: AI có nói ở ngôi thứ nhất như ứng viên không, có hỏi lại câu cũ không, có đi hết các câu hỏi không.
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
                elif m["type"] == "progress" and show:
                    where = "xong" if m["done"] else f"câu {m['q']}/{m['n']}"
                    print(f"   [{where}]")
                elif m["type"] == "error":
                    print(f"   LỖI: {m['msg']}")
                elif m["type"] == "turn_done":
                    if not show:
                        print(f"   AI:   {' '.join(said)}")
                    return

        await ws.send(json.dumps({"type": "start", "unit": unit}))
        await until_done(show=False)
        for i, answer in enumerate(answers, 1):
            print(f"{i:>2}. BẠN:  {answer}")
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
        print(f"\n===== Lần chạy {r}/{args.runs} =====")
        await run_once(args.url, args.unit, answers)


if __name__ == "__main__":
    asyncio.run(main())
