import { type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { ApiError, api } from "../../api/http";
import type { ContentList, UnitData } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { moved, shiftPhrase, slugify, splitList } from "../../lib/content";
import { FormError } from "../auth/AuthLayout";
import { AdminNav } from "./AdminNav";
import "../../styles/auth.css";

/** Form for one unit (docs/features/content-admin.md): every field of the units.json schema, plus an
 * AI draft for a new unit. The server checks the whole unit on save and lists what is wrong. */

type Lesson = NonNullable<UnitData["lesson"]>;

const blankStep = () => ({ hint: "", say: "" });
const blankPhrase = (): UnitData["phrases"][number] => ({ say: "", match: [] });
const blankQuestion = (phrase = 0) => ({ ask: "", simple: "", phrases: [phrase], steps: [blankStep(), blankStep()] });
const blankLesson = (phrases: number): Lesson => ({
  intro: "",
  intro_vi: "",
  vocab: [{ word: "", vi: "" }],
  sentences: Array.from({ length: Math.max(phrases, 1) }, (_, i) => ({ phrase: i, say: "", use: "", use_vi: "" })),
});
const blankUnit = (topic: string): UnitData => ({
  id: "",
  topic,
  title: "",
  scenario: "",
  goal: "",
  greeting: "",
  closing: "",
  vocab: "",
  phrases: [blankPhrase()],
  questions: [blankQuestion()],
});

// ----- Small inputs -----

function Text({
  label,
  value,
  onChange,
  hint,
  area,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  area?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {area ? (
        <textarea
          className="field-input"
          rows={2}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="field-input"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

/** A comma-separated list. Keeps the typed text (a trailing ", ") while the parsed list stays in sync. */
function ListInput({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  hint?: string;
}) {
  const [text, setText] = useState(value.join(", "));
  useEffect(() => {
    if (splitList(text).join("\n") !== value.join("\n")) setText(value.join(", "));
  }, [value]); // only outside changes (an AI draft) reset the text, not typing
  return (
    <Text
      label={label}
      value={text}
      hint={hint}
      onChange={(t) => {
        setText(t);
        onChange(splitList(t));
      }}
    />
  );
}

/** A list of blocks with add, remove and move buttons. */
function Items<T>({
  items,
  onChange,
  make,
  render,
  title,
  addLabel,
  min = 1,
  onRemove,
}: {
  items: T[];
  onChange: (items: T[]) => void;
  make: () => T;
  render: (item: T, set: (item: T) => void, i: number) => ReactNode;
  title: (i: number) => string;
  addLabel: string;
  min?: number;
  onRemove?: (i: number) => void; // instead of a plain removal (phrases also fix the indices pointing at them)
}) {
  return (
    <div className="items">
      {items.map((item, i) => (
        <div className="item" key={i}>
          <div className="item-head">
            <span className="item-title">{title(i)}</span>
            <div className="admin-actions">
              <button
                type="button"
                className="btn btn-sm"
                disabled={i === 0}
                onClick={() => onChange(moved(items, i, -1))}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={i === items.length - 1}
                onClick={() => onChange(moved(items, i, 1))}
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={items.length <= min}
                onClick={() => (onRemove ? onRemove(i) : onChange(items.filter((_, j) => j !== i)))}
              >
                Xóa
              </button>
            </div>
          </div>
          {render(item, (next) => onChange(items.map((x, j) => (j === i ? next : x))), i)}
        </div>
      ))}
      <button type="button" className="btn btn-sm" onClick={() => onChange([...items, make()])}>
        + {addLabel}
      </button>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="card admin-card">
      <h2>{title}</h2>
      {hint && <p className="admin-hint">{hint}</p>}
      {children}
    </section>
  );
}

// ----- AI draft -----

type Draft = { unit: UnitData; errors: string[]; notes: string[] };

function DraftPanel({ topic, onDraft }: { topic: string; onDraft: (d: Draft) => void }) {
  const [brief, setBrief] = useState("");
  const [lesson, setLesson] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      onDraft(await api<Draft>("/api/admin/draft", { body: { topic, brief, lesson } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      title="Nhờ AI soạn nháp"
      hint="Mô tả bài muốn tạo (tiếng Việt hay tiếng Anh đều được). AI viết nháp theo mẫu một bài có sẵn của chủ đề này, mất khoảng 1 đến 2 phút. Đọc lại và sửa trước khi lưu: AI có thể viết sai hoặc chưa tự nhiên."
    >
      <Text
        label="Bài này về gì?"
        area
        value={brief}
        placeholder="Ví dụ: gọi món ăn trưa với đồng nghiệp, hỏi món nào ngon, nói món mình thích"
        onChange={setBrief}
      />
      <label className="check-row">
        <input type="checkbox" checked={lesson} onChange={(e) => setLesson(e.target.checked)} />
        Soạn cả bài giảng (giáo viên giảng từng câu trước phần đóng vai)
      </label>
      <FormError error={error} />
      <div>
        <button type="button" className="btn btn-primary" disabled={busy || brief.trim().length < 3} onClick={run}>
          {busy ? "AI đang soạn… (1–2 phút)" : "Soạn nháp"}
        </button>
      </div>
    </Section>
  );
}

// ----- The form -----

export function UnitEditor() {
  const { unitId = "new" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const isNew = unitId === "new";
  const [list, setList] = useState<ContentList | null>(null);
  const [unit, setUnit] = useState<UnitData | null>(isNew ? blankUnit(params.get("topic") ?? "") : null);
  const [idTouched, setIdTouched] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState("");
  const [notes, setNotes] = useState<string[]>([]); // AI draft: valid but worth a look
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<ContentList>("/api/admin/content")
      .then(setList)
      .catch((e) => setError(e.message));
    if (!isNew)
      api<UnitData>(`/api/admin/units/${unitId}`)
        .then(setUnit)
        .catch((e) => setError(e.message));
  }, [unitId, isNew]);

  if (!unit)
    return (
      <>
        <AppBar />
        <main className="admin">
          <FormError error={error} />
        </main>
      </>
    );

  const set = (patch: Partial<UnitData>) => setUnit({ ...unit, ...patch });
  const phraseLabel = (i: number) => `${i + 1}. ${unit.phrases[i]?.say || "(chưa có)"}`;

  const removePhrase = (removed: number) =>
    set({
      phrases: unit.phrases.filter((_, j) => j !== removed),
      questions: unit.questions.map((q) => ({
        ...q,
        phrases: q.phrases.map((p) => shiftPhrase(p, removed)).filter((p): p is number => p !== null),
      })),
      lesson: unit.lesson && {
        ...unit.lesson,
        sentences: unit.lesson.sentences.map((s) => ({ ...s, phrase: shiftPhrase(s.phrase, removed) ?? 0 })),
      },
    });

  const save = async () => {
    setBusy(true);
    setError("");
    setErrors([]);
    setSaved("");
    // Optional fields left empty are dropped rather than stored as "".
    const clean: UnitData = { ...unit };
    for (const k of ["role", "partner", "vocab"] as const) if (!clean[k]?.trim()) delete clean[k];
    if (clean.followups === undefined || Number.isNaN(clean.followups)) delete clean.followups;
    try {
      await api(`/api/admin/units/${clean.id}`, { method: "PUT", body: clean });
      setSaved("Đã lưu. Người học thấy bài mới từ buổi tập sau.");
      if (isNew) navigate(`/admin/units/${clean.id}`, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setErrors(e instanceof ApiError ? e.errors : []);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AppBar />
      <main className="admin unit-editor">
        <h1>{isNew ? "Thêm bài" : `Sửa bài: ${unit.title}`}</h1>
        <AdminNav />
        <Link to="/admin/content">← Danh sách bài</Link>

        {isNew && (
          <DraftPanel
            topic={unit.topic}
            onDraft={(d) => {
              setUnit(d.unit);
              setIdTouched(true);
              setErrors(d.errors);
              setError(d.errors.length ? "Bản nháp còn vài chỗ cần sửa:" : "");
              setNotes(d.notes);
              setSaved("Đã có bản nháp. Đọc lại, sửa rồi bấm Lưu.");
            }}
          />
        )}
        {notes.length > 0 && (
          <section className="card admin-card draft-notes" role="status">
            <h2>Nên xem lại trong bản nháp</h2>
            <ul>
              {notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </section>
        )}

        <Section title="Thông tin chung">
          <div className="admin-grid">
            <label className="field">
              <span className="field-label">Chủ đề</span>
              <select className="field-input" value={unit.topic} onChange={(e) => set({ topic: e.target.value })}>
                <option value="">(chọn chủ đề)</option>
                {list?.topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </label>
            <Text
              label="Tên bài (tiếng Anh)"
              value={unit.title}
              onChange={(title) => set({ title, ...(isNew && !idTouched ? { id: slugify(title) } : {}) })}
            />
            <label className="field">
              <span className="field-label">Mã bài (id)</span>
              <input
                className="field-input"
                value={unit.id}
                disabled={!isNew}
                onChange={(e) => {
                  setIdTouched(true);
                  set({ id: e.target.value });
                }}
              />
              <span className="field-hint">
                {isNew
                  ? "Chữ thường, nối bằng dấu -. Không đổi được sau khi lưu."
                  : "Không đổi được: lịch sử dùng mã này."}
              </span>
            </label>
          </div>
          <Text
            label="Mục tiêu (tiếng Việt, hiện cho người học)"
            value={unit.goal}
            area
            onChange={(goal) => set({ goal })}
          />
          <Text
            label="Tình huống (tiếng Anh, gửi cho AI)"
            value={unit.scenario}
            area
            onChange={(scenario) => set({ scenario })}
          />
          <div className="admin-grid">
            <Text
              label="Câu chào mở đầu"
              value={unit.greeting}
              onChange={(greeting) => set({ greeting })}
              hint="AI nói trước câu hỏi đầu tiên."
            />
            <Text label="Câu kết thúc" value={unit.closing} onChange={(closing) => set({ closing })} />
          </div>
          <div className="admin-grid">
            <Text
              label="AI đóng vai (role)"
              value={unit.role ?? ""}
              onChange={(role) => set({ role })}
              hint='Ví dụ "a friendly COLLEAGUE having a relaxed coffee chat". Để trống: người phỏng vấn.'
            />
            <Text
              label="Tên vai hiện trên giao diện"
              value={unit.partner ?? ""}
              onChange={(partner) => set({ partner })}
              hint='Ví dụ "Đồng nghiệp". Để trống: "Người phỏng vấn".'
            />
            <label className="field">
              <span className="field-label">Số câu hỏi phụ tối đa mỗi câu</span>
              <input
                className="field-input"
                type="number"
                min={0}
                max={3}
                value={unit.followups ?? ""}
                placeholder="Mặc định"
                onChange={(e) => set({ followups: e.target.value === "" ? undefined : Number(e.target.value) })}
              />
            </label>
          </div>
          <Text
            label="Từ vựng giúp máy nghe đúng (tiếng Anh, cách nhau bằng dấu phẩy)"
            value={unit.vocab ?? ""}
            area
            onChange={(vocab) => set({ vocab })}
          />
        </Section>

        <Section
          title="Mẫu câu"
          hint='Mẫu câu người học cần dùng, kết thúc bằng "..." nếu là khung câu. "Nhận ra khi nói" là các cụm chữ thường mà câu trả lời chứa thì tính là đã dùng mẫu câu.'
        >
          <Items
            items={unit.phrases}
            onChange={(phrases) => set({ phrases })}
            onRemove={removePhrase}
            make={blankPhrase}
            title={(i) => `Mẫu câu ${i + 1}`}
            addLabel="Thêm mẫu câu"
            render={(p, setP) => (
              <div className="admin-grid">
                <Text label="Mẫu câu" value={p.say} onChange={(say) => setP({ ...p, say })} />
                <ListInput
                  label="Nhận ra khi nói"
                  value={p.match}
                  onChange={(match) => setP({ ...p, match })}
                  hint="Ví dụ: the best part was, the best thing was"
                />
                <ListInput
                  label="Chỉ gợi ý khi câu trả lời có (không bắt buộc)"
                  value={p.when ?? []}
                  onChange={(when) => setP({ ...p, ...(when.length ? { when } : { when: undefined }) })}
                  hint="Dùng cho câu đồng ý/phản đối, xem llm-prompt.md."
                />
              </div>
            )}
          />
        </Section>

        <Section
          title="Câu hỏi"
          hint="AI hỏi lần lượt. Mỗi câu hỏi luyện một hoặc vài mẫu câu, có câu hỏi dễ hơn khi người học trả lời chưa được, và 2–3 ý gợi ý để nói dài hơn."
        >
          <Items
            items={unit.questions}
            onChange={(questions) => set({ questions })}
            make={() => blankQuestion(0)}
            title={(i) => `Câu hỏi ${i + 1}`}
            addLabel="Thêm câu hỏi"
            render={(q, setQ) => (
              <>
                <Text label="Câu hỏi" value={q.ask} onChange={(ask) => setQ({ ...q, ask })} />
                <Text
                  label="Hỏi lại dễ hơn"
                  value={q.simple}
                  onChange={(simple) => setQ({ ...q, simple })}
                  hint="Dùng khi máy nghe chưa rõ hoặc câu trả lời chưa đủ ý."
                />
                <fieldset className="field phrase-picks">
                  <legend className="field-label">Luyện mẫu câu</legend>
                  {unit.phrases.map((_, i) => (
                    <label key={i} className="check-row">
                      <input
                        type="checkbox"
                        checked={q.phrases.includes(i)}
                        onChange={(e) =>
                          setQ({
                            ...q,
                            phrases: e.target.checked
                              ? [...q.phrases, i].sort((a, b) => a - b)
                              : q.phrases.filter((p) => p !== i),
                          })
                        }
                      />
                      {phraseLabel(i)}
                    </label>
                  ))}
                </fieldset>
                <div className="field">
                  <span className="field-label">Ý gợi ý để nói dài hơn</span>
                  <Items
                    items={q.steps}
                    onChange={(steps) => setQ({ ...q, steps })}
                    make={blankStep}
                    min={0}
                    title={(i) => `Ý ${i + 1}`}
                    addLabel="Thêm ý"
                    render={(st, setSt) => (
                      <div className="admin-grid">
                        <Text
                          label="Nhãn (tiếng Việt)"
                          value={st.hint}
                          onChange={(hint) => setSt({ ...st, hint })}
                          placeholder="Vì sao?"
                        />
                        <Text
                          label='Câu mở đầu (có "...")'
                          value={st.say}
                          onChange={(say) => setSt({ ...st, say })}
                          placeholder="That's because ..."
                        />
                      </div>
                    )}
                  />
                </div>
              </>
            )}
          />
        </Section>

        <Section
          title="Bài giảng"
          hint="Không bắt buộc. Có bài giảng thì giáo viên giảng từng câu cho người học đọc theo trước phần đóng vai, và bài chỉ tính là xong khi đủ cả hai phần."
        >
          <label className="check-row">
            <input
              type="checkbox"
              checked={!!unit.lesson}
              onChange={(e) => set({ lesson: e.target.checked ? blankLesson(unit.phrases.length) : undefined })}
            />
            Bài này có bài giảng
          </label>
          {unit.lesson && (
            <LessonFields
              lesson={unit.lesson}
              phrases={unit.phrases.length}
              phraseLabel={phraseLabel}
              onChange={(lesson) => set({ lesson })}
            />
          )}
        </Section>

        <div className="editor-bar">
          {error && (
            <div className="form-error" role="alert">
              {error}
              {errors.length > 0 && (
                <ul>
                  {errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {saved && <p className="form-ok">{saved}</p>}
          <div className="admin-actions start">
            <button className="btn btn-primary" disabled={busy || !unit.id || !unit.topic} onClick={save}>
              {busy ? "Đang lưu…" : "Lưu bài"}
            </button>
            {!isNew && (
              <Link className="btn" to={`/?unit=${unit.id}`}>
                Thử bài này
              </Link>
            )}
          </div>
        </div>
      </main>
    </>
  );
}

function LessonFields({
  lesson,
  phrases,
  phraseLabel,
  onChange,
}: {
  lesson: Lesson;
  phrases: number;
  phraseLabel: (i: number) => string;
  onChange: (l: Lesson) => void;
}) {
  return (
    <>
      <Text
        label="Lời mở đầu của giáo viên (tiếng Anh)"
        value={lesson.intro}
        area
        onChange={(intro) => onChange({ ...lesson, intro })}
      />
      <Text
        label="Bản dịch lời mở đầu"
        value={lesson.intro_vi}
        area
        onChange={(intro_vi) => onChange({ ...lesson, intro_vi })}
      />
      <div className="field">
        <span className="field-label">Từ quan trọng</span>
        <Items
          items={lesson.vocab}
          onChange={(vocab) => onChange({ ...lesson, vocab })}
          make={() => ({ word: "", vi: "" })}
          title={(i) => `Từ ${i + 1}`}
          addLabel="Thêm từ"
          render={(w, setW) => (
            <div className="admin-grid">
              <Text label="Từ (tiếng Anh)" value={w.word} onChange={(word) => setW({ ...w, word })} />
              <Text label="Nghĩa" value={w.vi} onChange={(vi) => setW({ ...w, vi })} />
            </div>
          )}
        />
      </div>
      <div className="field">
        <span className="field-label">Câu cần học (mỗi câu dựa trên một mẫu câu, viết đầy đủ, không có "...")</span>
        <Items
          items={lesson.sentences}
          onChange={(sentences) => onChange({ ...lesson, sentences })}
          make={() => ({ phrase: 0, say: "", use: "", use_vi: "" })}
          title={(i) => `Câu ${i + 1}`}
          addLabel="Thêm câu"
          render={(s, setS) => (
            <>
              <div className="admin-grid">
                <label className="field">
                  <span className="field-label">Mẫu câu</span>
                  <select
                    className="field-input"
                    value={s.phrase}
                    onChange={(e) => setS({ ...s, phrase: Number(e.target.value) })}
                  >
                    {Array.from({ length: phrases }, (_, i) => (
                      <option key={i} value={i}>
                        {phraseLabel(i)}
                      </option>
                    ))}
                  </select>
                </label>
                <Text label="Câu đọc theo" value={s.say} onChange={(say) => setS({ ...s, say })} />
              </div>
              <div className="admin-grid">
                <Text label="Giáo viên giảng (tiếng Anh)" value={s.use} area onChange={(use) => setS({ ...s, use })} />
                <Text label="Bản dịch" value={s.use_vi} area onChange={(use_vi) => setS({ ...s, use_vi })} />
              </div>
            </>
          )}
        />
      </div>
    </>
  );
}
