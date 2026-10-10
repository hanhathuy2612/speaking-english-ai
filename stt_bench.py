"""So sánh cấu hình STT trên CÙNG một bộ file ghi âm (không đọc lại mỗi lần).

Chuẩn bị:
  1. Đặt SAVE_AUDIO_DIR=recordings trong .env, chạy app, nói 15-20 câu.
     Mỗi câu thành recordings/<thời gian>.webm và <thời gian>.hyp.txt (chữ máy nghe được).
  2. Với mỗi câu, tạo <thời gian>.ref.txt chứa câu bạn THỰC SỰ đã nói
     (copy file .hyp.txt rồi sửa lại cho đúng là nhanh nhất).

Chạy (mỗi --config là model,device,compute,beam):
  python stt_bench.py recordings ^
    --config small.en,cpu,int8,1 ^
    --config distil-large-v3,cuda,float16,3 ^
    --config large-v3-turbo,cuda,float16,3 ^
    --prompt "Hi, I'm Huy. Java developer, microservices, payment system."

Kết quả: WER (tỉ lệ từ sai, thấp hơn là tốt hơn) và thời gian trung bình mỗi câu.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import cuda_dlls

cuda_dlls.add()  # trước khi nạp faster_whisper

from faster_whisper import WhisperModel  # noqa: E402

from parsing import word_errors  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--config", action="append", required=True)
    ap.add_argument("--prompt", default="", help="initial_prompt (từ vựng); để trống để tắt")
    ap.add_argument("--show", action="store_true", help="in từng câu máy nghe được")
    args = ap.parse_args()

    pairs = []
    for ref in sorted(Path(args.folder).glob("*.ref.txt")):
        audio = ref.with_name(ref.name.replace(".ref.txt", ".webm"))
        if audio.exists():
            pairs.append((audio, ref.read_text(encoding="utf-8").strip()))
    if not pairs:
        raise SystemExit(f"Không thấy cặp .webm + .ref.txt nào trong {args.folder}")
    print(f"{len(pairs)} câu, {sum(len(r.split()) for _, r in pairs)} từ tham chiếu\n")

    rows = []
    for cfg in args.config:
        name, device, compute, beam = cfg.split(",")
        try:
            model = WhisperModel(name, device=device, compute_type=compute,
                                 cpu_threads=int(os.getenv("STT_THREADS", "8")))
        except Exception as e:  # noqa: BLE001
            print(f"{cfg}: không nạp được ({e})")
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
            print(f"{cfg}: lỗi khi chạy ({e})")
            continue
        rows.append((cfg, errors / max(total, 1), elapsed / len(pairs)))
        del model

    print(f"\n{'cấu hình':42} {'WER':>7} {'giây/câu':>9}")
    for cfg, w, sec in sorted(rows, key=lambda r: r[1]):
        print(f"{cfg:42} {w:7.1%} {sec:9.2f}")


if __name__ == "__main__":
    main()
