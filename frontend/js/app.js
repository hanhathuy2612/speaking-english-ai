const $ = (s) => document.querySelector(s);
const st = {
  ws: null,
  holding: false,
  rec: null,
  chunks: [],
  pending: null,
  queue: [],
  playing: false,
  audio: null,
  turn: 0,
  lines: {},
  coachText: "",
  lastMe: null,
};

const setStatus = (t) => {
  $("#status").textContent = t || "";
};

/* ---------- WebSocket ---------- */
function init() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  st.ws = new WebSocket(`${proto}://${location.host}/ws`);
  st.ws.onopen = loadUnits;
  st.ws.onclose = () =>
    setStatus("Mất kết nối với máy chủ. Tải lại trang để thử lại.");
  st.ws.onmessage = onMessage;
}

async function loadUnits() {
  const list = await (await fetch("/api/units")).json();
  const sel = $("#unit");
  sel.innerHTML = "";
  list.forEach((u) => sel.add(new Option(u.title, u.id)));
  sel.onchange = startUnit;
  startUnit();
}

function startUnit() {
  stopPlayback();
  setStatus("Đang chuẩn bị bài…");
  st.ws.send(JSON.stringify({ type: "start", unit: $("#unit").value }));
}

function onMessage(e) {
  if (typeof e.data !== "string") {
    // binary frame = MP3 for the sentence announced just before
    enqueue(st.pending, e.data);
    st.pending = null;
    return;
  }
  const m = JSON.parse(e.data);
  switch (m.type) {
    case "started":
      renderUnit(m.unit);
      $("#sttLabel").textContent = "Nhận dạng giọng nói: " + m.unit.stt;
      break;
    case "status":
      setStatus(
        m.msg === "transcribing"
          ? "Đang nhận dạng giọng nói…"
          : "AI đang trả lời…",
      );
      break;
    case "transcript":
      st.turn += 1;
      $("#undo").hidden = true;
      $("#conf").textContent = m.conf == null ? "-" : m.conf.toFixed(2);
      if (m.unclear) {
        const d = addLine("me unclear", "Bạn (máy nghe chưa rõ)", m.text, m.speech);
        const note = d.querySelector(".speech") || document.createElement("div");
        note.className = "speech";
        note.textContent = "Máy nghe chưa rõ, bạn nói lại nhé. AI chưa trả lời câu này.";
        d.appendChild(note);
        setStatus("Máy nghe chưa rõ, bạn nói lại nhé.");
        break;
      }
      st.lastMe = { el: addLine("me", "Bạn", m.text, m.speech), turn: st.turn };
      markUsed(m.used);
      $("#coach").classList.remove("show");
      break;
    case "undone":
      stopPlayback();
      if (st.lastMe) {
        st.lastMe.el.remove();
        st.lines[st.lastMe.turn]?.remove();
        delete st.lines[st.lastMe.turn];
        st.lastMe = null;
      }
      markUsed(m.used);
      $("#coach").classList.remove("show");
      $("#summary").classList.remove("show");
      setStatus("Đã bỏ lượt vừa rồi. Giữ nút để trả lời lại.");
      break;
    case "progress":
      $("#progress").textContent = m.done
        ? `Đã xong ${m.n}/${m.n} câu hỏi`
        : `Câu hỏi ${m.q}/${m.n}`;
      break;
    case "summary":
      renderSummary(m);
      break;
    case "sentence":
      st.pending = { text: m.text, role: m.role, turn: st.turn };
      break;
    case "note":
      renderCoach(m);
      break;
    case "metrics":
      for (const k of [
        "stt_ms",
        "llm_first_ms",
        "first_audio_ms",
        "total_ms",
      ]) {
        $(`[data-k="${k}"]`).textContent = m[k]
          ? `${(m[k] / 1000).toFixed(1)} giây`
          : "-";
      }
      break;
    case "turn_done":
      $("#undo").hidden = !m.can_undo;
      if (!$("#status").textContent.startsWith("Máy nghe chưa rõ"))
        setStatus("Sẵn sàng. Giữ nút để nói.");
      break;
    case "error":
      setStatus("Lỗi: " + m.msg);
      break;
  }
}

/* ---------- Rendering ---------- */
function renderUnit(u) {
  $("#chat").innerHTML = "";
  $("#coach").classList.remove("show");
  $("#summary").classList.remove("show");
  $("#undo").hidden = true;
  st.turn = 0;
  st.lines = {};
  st.lastMe = null;
  $("#goal").textContent = u.goal;
  const ul = $("#phrases");
  ul.innerHTML = "";
  u.phrases.forEach((p) => {
    const li = document.createElement("li");
    li.innerHTML =
      '<span class="mark">✓</span><span class="serif"></span>';
    li.lastChild.textContent = p.say;
    ul.appendChild(li);
  });
}

function markUsed(used) {
  document
    .querySelectorAll("#phrases li")
    .forEach((li, i) => li.classList.toggle("used", used.includes(i)));
}

function addLine(kind, who, text, speech) {
  const div = document.createElement("div");
  div.className = `line ${kind}`;
  div.innerHTML = '<div class="who"></div><div class="text"></div>';
  div.querySelector(".who").textContent = who;
  div.querySelector(".text").textContent = text;
  if (speech && speech.words) {
    const s = document.createElement("div");
    s.className = "speech";
    let t =
      speech.wpm == null
        ? `${speech.words} từ (câu ngắn, chưa tính tốc độ), ${speech.long_pauses} lần ngắt dài`
        : `${speech.words} từ · khi nói ${speech.wpm_speaking} từ/phút · tính cả ngắt ${speech.wpm} từ/phút · ${speech.long_pauses} lần ngắt dài`;
    if (speech.low_conf.length)
      t += `. Máy nghe chưa chắc: ${speech.low_conf.join(", ")}`;
    s.textContent = t;
    div.appendChild(s);
  }
  $("#chat").appendChild(div);
  $("#chat").scrollTop = $("#chat").scrollHeight;
  return div;
}

function renderCoach(m) {
  if (!m.text) return;
  st.coachText = m.text;
  $("#coachFlag").textContent = m.retry
    ? "Chưa đủ ý. Hãy trả lời lại câu hỏi."
    : "";
  $("#coachLabel").textContent = m.retry
    ? "Câu mẫu để bạn nói theo"
    : "Cách nói tự nhiên hơn, thử nói lại";
  $("#coachText").textContent = m.text;
  $("#coach").classList.add("show");
}

function renderSummary(m) {
  const box = $("#summary");
  box.innerHTML = "<h2>Tổng kết phiên</h2>";
  const add = (t) => {
    const p = document.createElement("p");
    p.textContent = t;
    box.appendChild(p);
  };
  add(`Đã trả lời đủ ${m.questions} câu hỏi trong ${m.turns} lượt.`);
  add(`Mẫu câu đã dùng (${m.phrases_used.length}): ${m.phrases_used.join(" | ") || "chưa có"}`);
  if (m.phrases_missed.length)
    add(`Chưa dùng: ${m.phrases_missed.join(" | ")}`);
  if (m.wpm != null)
    add(`Tốc độ trung bình: khi nói ${m.wpm_speaking} từ/phút, tính cả ngắt ${m.wpm} từ/phút.`);
  if (m.spoken_turns)
    add(`Ngắt dài: ${m.long_pauses} lần trong ${m.spoken_turns} lượt nói.`);
  box.classList.add("show");
}

$("#undo").onclick = () => {
  $("#undo").hidden = true;
  st.ws.send(JSON.stringify({ type: "undo" }));
};

$("#coachPlay").onclick = () => {
  if (st.coachText)
    st.ws.send(JSON.stringify({ type: "say_it", text: st.coachText }));
};

/* ---------- Queued audio playback ---------- */
function enqueue(meta, data) {
  const url = URL.createObjectURL(
    new Blob([data], { type: "audio/mpeg" }),
  );
  st.queue.push({ meta, url });
  if (!st.playing) playNext();
}

function playNext() {
  const item = st.queue.shift();
  if (!item) {
    st.playing = false;
    return;
  }
  st.playing = true;
  if (item.meta.role === "ai") appendAi(item.meta.turn, item.meta.text);
  const a = new Audio(item.url);
  st.audio = a;
  const done = () => {
    URL.revokeObjectURL(item.url);
    playNext();
  };
  a.onended = done;
  a.onerror = done;
  a.play().catch(done);
}

function appendAi(turn, text) {
  let line = st.lines[turn];
  if (!line) {
    line = addLine("ai", "Người phỏng vấn", "");
    st.lines[turn] = line;
  }
  const el = line.querySelector(".text");
  el.textContent = el.textContent ? `${el.textContent} ${text}` : text;
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function stopPlayback() {
  st.queue.forEach((i) => URL.revokeObjectURL(i.url));
  st.queue = [];
  if (st.audio) {
    st.audio.pause();
    st.audio = null;
  }
  st.playing = false;
}

/* ---------- Recording: hold to talk ---------- */
async function startRec() {
  if (st.holding) return;
  st.holding = true;
  stopPlayback();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
    });
    if (!st.holding) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "";
    const rec = new MediaRecorder(
      stream,
      mime ? { mimeType: mime } : undefined,
    );
    st.chunks = [];
    rec.ondataavailable = (e) => st.chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(st.chunks, { type: rec.mimeType });
      if (blob.size < 3000) {
        setStatus("Ghi âm quá ngắn. Hãy giữ nút lâu hơn.");
        return;
      }
      setStatus("Đang gửi…");
      st.ws.send(blob);
    };
    rec.start();
    st.rec = rec;
    $("#talk").classList.add("rec");
    $("#talk").textContent = "Đang ghi âm. Thả ra để gửi";
  } catch (err) {
    st.holding = false;
    setStatus("Không mở được micro: " + err.message);
  }
}

function stopRec() {
  st.holding = false;
  if (!st.rec) return;
  st.rec.stop();
  st.rec = null;
  $("#talk").classList.remove("rec");
  $("#talk").textContent = "Giữ để nói";
}

const talk = $("#talk");
talk.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  startRec();
});
["pointerup", "pointerleave", "pointercancel"].forEach((ev) =>
  talk.addEventListener(ev, stopRec),
);

$("#typed").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || !e.target.value.trim()) return;
  stopPlayback();
  st.ws.send(JSON.stringify({ type: "text", text: e.target.value }));
  e.target.value = "";
});

init();
