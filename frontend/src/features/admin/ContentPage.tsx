import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/http";
import type { ContentList, ContentTopic, ContentUnitRow } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Chip } from "../../components/ui";
import { fmtDate } from "../../lib/format";
import { Field, FormError, onSubmit } from "../auth/AuthLayout";
import { AdminNav } from "./AdminNav";
import "../../styles/auth.css";

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

function TopicForm({ topic, onSaved }: { topic: ContentTopic; onSaved: () => void }) {
  const [title, setTitle] = useState(topic.title);
  const [description, setDescription] = useState(topic.description);
  const [error, setError] = useState("");
  const save = async () => {
    try {
      await api(`/api/admin/topics/${topic.id}`, { method: "PUT", body: { title, description } });
      onSaved();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <form className="topic-form" onSubmit={onSubmit(save)}>
      <Field label="Tên chủ đề" required value={title} onChange={(e) => setTitle(e.target.value)} />
      <Field label="Mô tả" required value={description} onChange={(e) => setDescription(e.target.value)} />
      <FormError error={error} />
      <div className="admin-actions start">
        <button className="btn btn-primary btn-sm">Lưu</button>
        <button type="button" className="btn btn-sm" onClick={onSaved}>
          Hủy
        </button>
      </div>
    </form>
  );
}

function UnitRow({
  u,
  first,
  last,
  onMove,
  onDelete,
  onRestore,
}: {
  u: ContentUnitRow;
  first: boolean;
  last: boolean;
  onMove: (step: -1 | 1) => void;
  onDelete: () => void;
  onRestore: () => void;
}) {
  return (
    <li className={`content-unit${u.deleted ? " deleted" : ""}`}>
      <div className="content-unit-main">
        <div className="content-unit-title">
          {u.deleted ? u.title : <Link to={`/admin/units/${u.id}`}>{u.title}</Link>}
          <span className="content-unit-id">{u.id}</span>
        </div>
        <div className="content-unit-meta">
          {u.questions} câu hỏi
          {u.lesson && <Chip>Có bài giảng</Chip>}
          {u.invalid && (
            <Chip tone="warning" title="Không qua kiểm tra hợp lệ nên chưa dùng trong app. Mở bài để xem lỗi và sửa.">
              Có lỗi, đang tạm ẩn
            </Chip>
          )}
          {u.deleted ? (
            <Chip tone="warning">Đã xóa</Chip>
          ) : u.source === "admin" ? (
            <Chip tone="success" title="Đã sửa trên web: không còn tự cập nhật theo units.json">
              Đã sửa{u.updated_by ? ` · ${u.updated_by}` : ""}
              {u.updated_at ? ` · ${fmtDate(u.updated_at)}` : ""}
            </Chip>
          ) : (
            <Chip title="Theo units.json trong mã nguồn">Nội dung gốc</Chip>
          )}
        </div>
      </div>
      <div className="admin-actions">
        {u.deleted ? (
          <button className="btn btn-sm" onClick={onRestore}>
            Khôi phục
          </button>
        ) : (
          <>
            <button
              className="btn btn-sm"
              disabled={first}
              onClick={() => onMove(-1)}
              aria-label={`Đưa ${u.title} lên`}
            >
              ↑
            </button>
            <button
              className="btn btn-sm"
              disabled={last}
              onClick={() => onMove(1)}
              aria-label={`Đưa ${u.title} xuống`}
            >
              ↓
            </button>
            <Link className="btn btn-sm" to={`/admin/units/${u.id}`}>
              Sửa
            </Link>
            <button className="btn btn-sm" onClick={onDelete}>
              Xóa
            </button>
          </>
        )}
      </div>
    </li>
  );
}

export function ContentPage() {
  const [data, setData] = useState<ContentList | null>(null);
  const [editing, setEditing] = useState<string | null>(null); // topic id whose texts are being edited
  const [message, setMessage] = useState("");

  const load = useCallback(() => {
    api<ContentList>("/api/admin/content")
      .then(setData)
      .catch((e) => setMessage(errorText(e)));
  }, []);
  useEffect(load, [load]);

  const act = async (run: () => Promise<unknown>, done: string) => {
    try {
      await run();
      setMessage(done);
    } catch (e) {
      setMessage(errorText(e));
    }
    load();
  };

  const move = (u: ContentUnitRow, step: -1 | 1) => {
    if (!data) return;
    // Swap with the neighbour in the same topic; units of other topics may sit between them.
    const live = data.units.filter((x) => !x.deleted && x.topic === u.topic);
    const other = live[live.findIndex((x) => x.id === u.id) + step];
    const ids = data.units.filter((x) => !x.deleted).map((x) => x.id);
    const [a, b] = [ids.indexOf(u.id), ids.indexOf(other.id)];
    [ids[a], ids[b]] = [ids[b], ids[a]];
    void act(() => api("/api/admin/order", { body: { ids } }), "Đã đổi thứ tự bài trong chủ đề.");
  };

  const stageOf = (topicId: string) => data?.stages.find((s) => s.topics.includes(topicId))?.title;

  return (
    <>
      <AppBar />
      <main className="admin">
        <h1>Quản trị</h1>
        <AdminNav />
        <p className="admin-hint">
          Bài học xếp theo chủ đề, đúng thứ tự người học gặp trên lộ trình. Sửa xong là người học thấy ngay ở buổi tập
          sau. Bài đã sửa trên web không còn tự cập nhật theo <code>units.json</code> trong mã nguồn.
        </p>
        {message && (
          <p className="admin-message" role="status">
            {message}
          </p>
        )}
        {data?.topics.map((t) => {
          const list = data.units.filter((u) => u.topic === t.id);
          const live = list.filter((u) => !u.deleted);
          return (
            <section key={t.id} className="card admin-card">
              {editing === t.id ? (
                <TopicForm
                  topic={t}
                  onSaved={() => {
                    setEditing(null);
                    load();
                  }}
                />
              ) : (
                <div className="content-topic-head">
                  <div>
                    <h2>{t.title}</h2>
                    <p className="admin-hint">
                      {t.description}
                      {stageOf(t.id) && ` · Giai đoạn: ${stageOf(t.id)}`}
                    </p>
                  </div>
                  <div className="admin-actions">
                    <button className="btn btn-sm" onClick={() => setEditing(t.id)}>
                      Sửa chủ đề
                    </button>
                    <Link className="btn btn-sm btn-primary" to={`/admin/units/new?topic=${t.id}`}>
                      Thêm bài
                    </Link>
                  </div>
                </div>
              )}
              <ol className="content-units">
                {list.map((u) => (
                  <UnitRow
                    key={u.id}
                    u={u}
                    first={live[0]?.id === u.id}
                    last={live[live.length - 1]?.id === u.id}
                    onMove={(step) => move(u, step)}
                    onDelete={() => {
                      if (window.confirm(`Xóa bài "${u.title}"? Lịch sử luyện tập vẫn giữ, bài khôi phục lại được.`))
                        void act(() => api(`/api/admin/units/${u.id}`, { method: "DELETE" }), `Đã xóa "${u.title}".`);
                    }}
                    onRestore={() =>
                      void act(
                        () => api(`/api/admin/units/${u.id}/restore`, { body: {} }),
                        `Đã khôi phục "${u.title}".`,
                      )
                    }
                  />
                ))}
              </ol>
            </section>
          );
        })}
      </main>
    </>
  );
}
