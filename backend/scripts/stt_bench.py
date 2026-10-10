"""Compare STT configs on the SAME set of recordings (never re-record per config).

Quick setup: open http://localhost:8000/bench and read the 18 sentences.
Each one becomes recordings/bench/NN.webm + NN.ref.txt (reference text included).
Recordings from the main app (recordings/*.webm) also work once a <name>.ref.txt sits next to them.

Run from backend/ (each --config is model,device,compute,beam):
  python -m scripts.stt_bench --config large-v3-turbo,cuda,float16,3 --config distil-large-v3,cuda,float16,3 --show
  python -m scripts.stt_bench ../recordings --config ...   # another folder (default: recordings/bench)

Output: WER (word error rate, lower is better) and average seconds per clip.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from app.core.config import BENCH_DIR
from app.core.cuda import add_cuda_dlls

add_cuda_dlls()  # before importing faster_whisper

from faster_whisper import WhisperModel  # noqa: E402

from app.utils.parsing import word_errors  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", default=str(BENCH_DIR), help="default: recordings/bench")
    ap.add_argument("--config", action="append", required=True)
    ap.add_argument("--prompt", default="", help="initial_prompt (vocabulary); empty to disable")
    ap.add_argument("--show", action="store_true", help="print each hypothesis")
    args = ap.parse_args()

    pairs = []
    for ref in sorted(Path(args.folder).glob("*.ref.txt")):
        audio = ref.with_name(ref.name.replace(".ref.txt", ".webm"))
        if audio.exists():
            pairs.append((audio, ref.read_text(encoding="utf-8").strip()))
    if not pairs:
        raise SystemExit(f"No .webm + .ref.txt pairs found in {args.folder}")
    print(f"{len(pairs)} clips, {sum(len(r.split()) for _, r in pairs)} reference words\n")

    rows = []
    for cfg in args.config:
        name, device, compute, beam = cfg.split(",")
        try:
            model = WhisperModel(name, device=device, compute_type=compute,
                                 cpu_threads=int(os.getenv("STT_THREADS", "8")))
        except Exception as e:  # noqa: BLE001
            print(f"{cfg}: failed to load ({e})")
            continue
        errors = total = 0
        elapsed = 0.0
        try:
            for audio, ref in pairs:
                t = time.perf_counter()
                segs, _ = model.transcribe(
                    str(audio), language="en", beam_size=int(beam), vad_filter=True,
                    condition_on_previous_text=False, initial_prompt=args.prompt or None,
                )
                hyp = " ".join(s.text.strip() for s in segs)
                elapsed += time.perf_counter() - t
                e, n = word_errors(ref, hyp)
                errors, total = errors + e, total + n
                if args.show:
                    print(f"  [{cfg}] {e}/{n}  {hyp}")
        except Exception as e:  # noqa: BLE001
            print(f"{cfg}: failed while running ({e})")
            continue
        rows.append((cfg, errors / max(total, 1), elapsed / len(pairs)))
        del model

    print(f"\n{'config':42} {'WER':>7} {'sec/clip':>9}")
    for cfg, w, sec in sorted(rows, key=lambda r: r[1]):
        print(f"{cfg:42} {w:7.1%} {sec:9.2f}")


if __name__ == "__main__":
    main()
