import { useEffect, useState } from "react";
import { api, postAudio } from "../../api/http";
import type { BenchItem } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { MicIcon } from "../../components/Icons";
import { Chip, type Status, StatusLine } from "../../components/ui";
import { useMic } from "../../hooks/useMic";
import "../../styles/bench.css";

/** Read-aloud page: records each sentence with its known reference for scripts/stt_bench.py. */
export function BenchPage() {
  const [items, setItems] = useState<BenchItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });

  useEffect(() => {
    document.title = "Đọc theo câu mẫu";
    void (async () => {
      const list = await api<BenchItem[]>("/api/bench");
      setItems(list);
      const first = list.findIndex((x) => !x.done);
      setIdx(first < 0 ? 0 : first);
    })();
  }, []);

  const doneCount = items.filter((x) => x.done).length;
  const allDone = items.length > 0 && doneCount === items.length;

  useEffect(() => {
    if (items.length)
      setStatus({ text: allDone ? "Đã thu đủ. Có thể chạy scripts/stt_bench để đo." : "Sẵn sàng", state: "ready" });
  }, [allDone, items.length]);

  const mic = useMic({
    onRecorded: async (blob) => {
      const i = idx;
      await postAudio(`/api/bench/${i}`, blob);
      const next = items.map((x, k) => (k === i ? { ...x, done: true } : x));
      setItems(next);
      const nextIdx = next.findIndex((x, k) => k > i && !x.done);
      setIdx(nextIdx >= 0 ? nextIdx : Math.min(i + 1, next.length - 1));
      setStatus({ text: "Đã lưu. Đọc câu tiếp theo.", state: "ready" });
    },
    onTooShort: () => setStatus({ text: "Thu quá ngắn, hãy đọc hết câu rồi mới bấm dừng.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
    onRecording: () => setStatus({ text: "Đang ghi âm", state: "recording" }),
  });

  return (
    <>
      <AppBar />
      <main className="bench">
        <div className="bench-head">
          <h1>Đọc theo câu mẫu</h1>
          <p className="lead">
            Đọc tự nhiên như khi nói chuyện, không cần chậm hay cố phát âm chuẩn. Kết quả dùng để đo độ chính xác nhận
            dạng giọng nói.
          </p>
        </div>

        <section className="card reader">
          <div className="reader-top">
            <span className="eyebrow">{items.length > 0 && `Câu ${idx + 1}/${items.length}`}</span>
            <Chip tone={allDone ? "success" : ""}>
              Đã thu {doneCount}/{items.length}
            </Chip>
          </div>
          <p className="current">{items[idx]?.text}</p>
          <div className="reader-actions">
            <button
              className={`mic${mic.recording ? " rec" : ""}`}
              aria-label={mic.recording ? "Đang thu, bấm để lưu" : "Bấm để đọc"}
              {...mic.buttonProps}
            >
              <MicIcon />
            </button>
            <div>
              <p className="talk-label">
                {mic.recording ? "Đang thu… bấm lần nữa để lưu" : "Bấm nút (hoặc giữ phím Space) để đọc"}
              </p>
              <StatusLine status={status} />
            </div>
          </div>
        </section>

        <section className="card list-card">
          <p className="eyebrow">Tất cả câu (bấm để thu lại)</p>
          <ol className="list">
            {items.map((it, i) => (
              <li
                key={it.text}
                className={[it.done && "done", i === idx && "active"].filter(Boolean).join(" ")}
                tabIndex={0}
                role="button"
                onClick={() => setIdx(i)}
                onKeyDown={(e) => e.key === "Enter" && setIdx(i)}
              >
                {it.text}
              </li>
            ))}
          </ol>
        </section>
      </main>
    </>
  );
}
