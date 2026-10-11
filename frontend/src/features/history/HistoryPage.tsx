import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import type { HistorySession } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { TrashIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { type Delta, fmtDate, fmtNum, latestWithDelta } from "../../lib/format";
import "../../styles/history.css";
import { LineChart } from "./LineChart";
import { SessionDetail } from "./SessionDetail";

function Tile({ label, value, unit = "", delta }: { label: string; value: string; unit?: string; delta?: Delta }) {
  return (
    <div className="card tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">
        <span>{value}</span>
        <span className="tile-unit">{unit}</span>
      </div>
      <div className={`tile-delta${delta?.tone ? ` ${delta.tone}` : ""}`}>{delta?.text}</div>
    </div>
  );
}

function Tiles({ sessions }: { sessions: HistorySession[] }) {
  const completed = sessions.filter((s) => s.completed).length;
  const spoken = sessions.reduce((a, s) => a + s.spoken_turns, 0);
  const words = sessions.reduce((a, s) => a + s.words, 0);
  const speed = latestWithDelta(sessions.map((s) => s.wpm_speaking), false);
  const pauses = latestWithDelta(sessions.map((s) => s.pauses_per_100_words), true);
  const shadow = latestWithDelta(sessions.map((s) => s.shadow_accuracy), false);
  return (
    <section className="tiles" aria-label="Tóm tắt">
      <Tile label="Buổi tập" value={`${sessions.length}`} delta={{ text: `${completed} buổi hoàn thành đủ câu hỏi` }} />
      <Tile label="Lượt nói bằng giọng" value={`${spoken}`} delta={{ text: `${words} từ đã nói` }} />
      <Tile label="Tốc độ khi nói, buổi gần nhất" value={fmtNum(speed.value)} unit="từ/phút" delta={speed.delta} />
      <Tile label="Ngắt dài / 100 từ, buổi gần nhất" value={fmtNum(pauses.value)} delta={pauses.delta} />
      <Tile
        label="Đọc đúng khi nói lại, buổi gần nhất"
        value={fmtNum(shadow.value)}
        unit="%"
        delta={shadow.value == null ? { text: "Chưa có lần nói lại câu mẫu nào" } : shadow.delta}
      />
    </section>
  );
}

type TableProps = {
  sessions: HistorySession[];
  openId: number | null;
  onOpen: (s: HistorySession) => void;
  onDelete: (s: HistorySession) => void;
};

function SessionsTable({ sessions, openId, onOpen, onDelete }: TableProps) {
  return (
    <section className="card table-card">
      <h2>Các buổi tập</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Thời gian</th>
              <th scope="col">Bài</th>
              <th scope="col" className="num">Lượt nói</th>
              <th scope="col" className="num">Từ/phút khi nói</th>
              <th scope="col" className="num">Ngắt / 100 từ</th>
              <th scope="col" className="num">Mẫu câu</th>
              <th scope="col" className="num">Nói lại</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">
                <span className="sr-only">Câu trả lời và ghi âm</span>
              </th>
              <th scope="col">
                <span className="sr-only">Xóa</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {[...sessions].reverse().map((s) => (
              <tr key={s.id} className={s.id === openId ? "selected" : undefined}>
                <td>{fmtDate(s.started_at)}</td>
                <td>{s.unit_title}</td>
                <td className="num">
                  {s.spoken_turns}/{s.turns}
                </td>
                <td className="num">{fmtNum(s.wpm_speaking)}</td>
                <td className="num">{fmtNum(s.pauses_per_100_words)}</td>
                <td className="num">
                  {s.phrases_used}/{s.phrase_total}
                </td>
                <td className="num">
                  {s.shadow_accuracy == null ? "–" : `${s.shadow_accuracy}% · ${s.shadow_attempts} lần`}
                </td>
                <td>
                  <Chip tone={s.completed ? "success" : ""}>{s.completed ? "Hoàn thành" : "Dở dang"}</Chip>
                </td>
                <td>
                  <button
                    className="btn btn-sm"
                    aria-pressed={s.id === openId}
                    aria-label={`Xem câu trả lời và nghe lại buổi ${fmtDate(s.started_at)}`}
                    onClick={() => onOpen(s)}
                  >
                    Xem
                  </button>
                </td>
                <td>
                  <button
                    className="btn btn-ghost"
                    aria-label={`Xóa buổi tập ${fmtDate(s.started_at)}`}
                    onClick={() => onDelete(s)}
                  >
                    <TrashIcon />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function HistoryPage() {
  const [data, setData] = useState<{ enabled: boolean; sessions: HistorySession[] } | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setData(await (await fetch("/api/history/sessions")).json());
  }, []);

  useEffect(() => {
    document.title = "Tiến bộ luyện nói";
    void load();
  }, [load]);

  const onDelete = async (s: HistorySession) => {
    if (!confirm(`Xóa buổi tập ${fmtDate(s.started_at)} (${s.unit_title})? Không thể hoàn tác.`)) return;
    await fetch(`/api/history/sessions/${s.id}`, { method: "DELETE" });
    if (s.id === openId) setOpenId(null);
    void load();
  };

  const sessions = data?.sessions ?? [];
  const open = sessions.find((s) => s.id === openId);
  const message = !data
    ? null
    : !data.enabled
      ? "Lịch sử đang tắt (HISTORY_DB trong .env để trống)."
      : !sessions.length
        ? "Chưa có buổi tập nào. Hãy vào Phòng tập và trả lời vài câu, kết quả sẽ hiện ở đây."
        : null;

  return (
    <>
      <AppBar />
      <main className="page">
        <div className="page-head">
          <h1>Tiến bộ luyện nói</h1>
          <p className="lead">Tính trên các lượt trả lời bằng giọng nói, máy nghe rõ. Tốc độ chỉ tính câu từ 10 từ trở lên.</p>
        </div>

        {message && <p className="card empty">{message}</p>}

        {!message && sessions.length > 0 && (
          <div id="content">
            <Tiles sessions={sessions} />
            <section className="charts">
              <figure className="card chart-card">
                <figcaption>
                  <h2>Tốc độ khi nói</h2>
                  <p>Từ/phút, trung bình mỗi buổi. Cao hơn là trôi chảy hơn.</p>
                </figcaption>
                <LineChart sessions={sessions} field="wpm_speaking" unit="từ/phút" />
              </figure>
              <figure className="card chart-card">
                <figcaption>
                  <h2>Ngắt dài trên 100 từ</h2>
                  <p>Số lần dừng quá 0,7 giây. Thấp hơn là tốt hơn.</p>
                </figcaption>
                <LineChart sessions={sessions} field="pauses_per_100_words" unit="lần / 100 từ" />
              </figure>
              <figure className="card chart-card">
                <figcaption>
                  <h2>Đọc đúng khi nói lại câu mẫu</h2>
                  <p>% từ máy nghe đúng, gộp mọi lần nói lại trong buổi. Cao hơn là phát âm rõ hơn.</p>
                </figcaption>
                <LineChart sessions={sessions} field="shadow_accuracy" unit="%" max={100} />
              </figure>
            </section>
            <SessionsTable
              sessions={sessions}
              openId={openId}
              onOpen={(s) => setOpenId((id) => (id === s.id ? null : s.id))}
              onDelete={onDelete}
            />
            {open && <SessionDetail session={open} onClose={() => setOpenId(null)} />}
          </div>
        )}
        <p className="history-foot">
          Máy nghe sai nhiều từ bạn nói đúng? Đo lại độ chính xác nhận dạng ở trang{" "}
          <Link to="/bench">Đo nhận dạng</Link>.
        </p>
      </main>
    </>
  );
}
