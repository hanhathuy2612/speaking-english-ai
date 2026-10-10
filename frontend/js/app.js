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

// state: ready | busy | recording | warn | error (drives the colored dot)
const setStatus = (text, state = "") => {
  const el = $("#status");
  el.textContent = text || "";
  el.dataset.state = state;
};

/* ---------- WebSocket ---------- */
function init() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  st.ws = new WebSocket(`${proto}://${location.host}/ws`);
  st.ws.onopen = loadUnits;
  st.ws.onclose = () => setStatus("Mất kết nối với máy chủ. Tải lại trang để thử lại.", "error");
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
  setStatus("Đang chuẩn bị bài…", "busy");
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
      $("#sttLabel").textContent = m.unit.stt;
      break;
    case "status":
      setStatus(m.msg === "transcribing" ? "Đang nhận dạng giọng nói…" : "AI đang trả lời…", "busy");
      break;
    case "transcript":
      st.turn += 1;
      $("#undo").hidden = true;
      $("#conf").textContent = m.conf == null ? "-" : m.conf.toFixed(2);
      if (m.unclear) {
        const el = addMessage("me", "Bạn", m.text, m.speech, { unclear: true });
        el.querySelector(".meta").prepend(chip("Máy nghe chưa rõ, AI chưa trả lời", "warning"));
        setStatus("Máy nghe chưa rõ, bạn nói lại nhé.", "warn");
        break;
      }
      st.lastMe = { el: addMessage("me", "Bạn", m.text, m.speech), turn: st.turn };
      markUsed(m.used);
      $("#coach").hidden = true;
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
      $("#coach").hidden = true;
      $("#chat .summary")?.remove();
      setStatus("Đã bỏ lượt vừa rồi. Hãy trả lời lại.", "ready");
      break;
    case "progress":
      renderProgress(m);
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
      for (const k of ["stt_ms", "llm_first_ms", "first_audio_ms", "total_ms"]) {
        $(`[data-k="${k}"]`).textContent = m[k] ? `${(m[k] / 1000).toFixed(1)} giây` : "-";
      }
      break;
    case "turn_done":
      $("#undo").hidden = !m.can_undo;
      if ($("#status").dataset.state !== "warn") setStatus("Sẵn sàng, mời bạn trả lời", "ready");
      break;
    case "error":
      setStatus("Lỗi: " + m.msg, "error");
      break;
  }
}

/* ---------- Rendering ---------- */
function renderUnit(u) {
  $("#chat").innerHTML = "";
  $("#coach").hidden = true;
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
      '<span class="mark" aria-hidden="true"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg></span><span></span>';
    li.lastChild.textContent = p.say;
    ul.appendChild(li);
  });
  markUsed([]);
}

function renderProgress(m) {
  const done = m.done ? m.n : m.q - 1;
  $("#progress").textContent = m.done ? `Hoàn thành ${m.n}/${m.n}` : `Câu hỏi ${m.q}/${m.n}`;
  $("#progressFill").style.width = `${(done / m.n) * 100}%`;
  $(".progress").classList.toggle("done", m.done);
}

function markUsed(used) {
  const items = document.querySelectorAll("#phrases li");
  items.forEach((li, i) => li.classList.toggle("used", used.includes(i)));
  $("#phraseCount").textContent = `${used.length}/${items.length}`;
  $("#phraseCount").classList.toggle("chip-success", items.length > 0 && used.length === items.length);
}

function chip(text, tone = "") {
  const el = document.createElement("span");
  el.className = tone ? `chip chip-${tone}` : "chip";
  el.textContent = text;
  return el;
}

function speechChips(speech) {
  if (!speech || !speech.words) return [];
  const out = [chip(`${speech.words} từ`)];
  if (speech.wpm == null) out.push(chip("Câu ngắn, chưa tính tốc độ"));
  else {
    out.push(chip(`Khi nói ${speech.wpm_speaking} từ/phút`));
    out.push(chip(`Tính cả ngắt ${speech.wpm} từ/phút`));
  }
  out.push(chip(`${speech.long_pauses} lần ngắt dài`, speech.long_pauses > 2 ? "warning" : ""));
  if (speech.low_conf.length) out.push(chip(`Máy nghe chưa chắc: ${speech.low_conf.join(", ")}`, "warning"));
  return out;
}

// kind: "ai" | "me"
function addMessage(kind, who, text, speech, opts = {}) {
  const el = document.createElement("div");
  el.className = `msg ${kind}${opts.unclear ? " unclear" : ""}`;
  el.innerHTML =
    '<div class="avatar" aria-hidden="true"></div><div class="msg-body"><div class="who"></div><div class="bubble"></div><div class="meta"></div></div>';
  el.querySelector(".avatar").textContent = kind === "ai" ? "AI" : "Bạn";
  el.querySelector(".who").textContent = who;
  el.querySelector(".bubble").textContent = text;
  el.querySelector(".meta").append(...speechChips(speech));
  $("#chat").appendChild(el);
  scrollChat();
  return el;
}

function scrollChat() {
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function renderCoach(m) {
  if (!m.text) return;
  st.coachText = m.text;
  $("#coachFlag").textContent = "Chưa đủ ý, hãy trả lời lại";
  $("#coachFlag").hidden = !m.retry;
  $("#coachLabel").textContent = m.retry ? "Câu mẫu để bạn nói theo" : "Cách nói tự nhiên hơn, thử nói lại";
  $("#coachText").textContent = m.text;
  $("#coach").hidden = false;
}

// Appended to the end of the conversation as the closing card of the session.
function renderSummary(m) {
  $("#chat .summary")?.remove();
  const box = document.createElement("section");
  box.className = "card summary";
  const h = document.createElement("h2");
  h.innerHTML =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--success)" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg><span>Tổng kết phiên</span>';
  box.appendChild(h);

  const stats = document.createElement("div");
  stats.className = "stats";
  const stat = (value, label) => {
    const d = document.createElement("div");
    d.className = "stat";
    d.innerHTML = '<div class="stat-value"></div><div class="stat-label"></div>';
    d.firstChild.textContent = value;
    d.lastChild.textContent = label;
    stats.appendChild(d);
  };
  stat(`${m.questions}`, `câu hỏi, trong ${m.turns} lượt`);
  stat(`${m.phrases_used.length}/${m.phrases_used.length + m.phrases_missed.length}`, "mẫu câu đã dùng");
  if (m.wpm != null) stat(`${m.wpm_speaking}`, "từ/phút khi nói");
  if (m.spoken_turns) stat(`${m.long_pauses}`, `lần ngắt dài / ${m.spoken_turns} lượt nói`);
  box.appendChild(stats);

  const row = (label, items, tone) => {
    if (!items.length) return;
    const r = document.createElement("div");
    r.className = "summary-row";
    r.innerHTML = '<p class="eyebrow"></p><div class="chips"></div>';
    r.firstChild.textContent = label;
    r.lastChild.append(...items.map((t) => chip(t, tone)));
    box.appendChild(r);
  };
  row("Đã dùng", m.phrases_used, "success");
  row("Chưa dùng", m.phrases_missed, "");
  const link = document.createElement("a");
  link.className = "btn btn-sm summary-link";
  link.href = "/history";
  link.textContent = "Xem tiến bộ qua các buổi";
  box.appendChild(link);
  $("#chat").appendChild(box);
  scrollChat();
}

$("#undo").onclick = () => {
  $("#undo").hidden = true;
  st.ws.send(JSON.stringify({ type: "undo" }));
};

$("#coachPlay").onclick = () => {
  if (st.coachText) st.ws.send(JSON.stringify({ type: "say_it", text: st.coachText }));
};

/* ---------- Queued audio playback ---------- */
function enqueue(meta, data) {
  const url = URL.createObjectURL(new Blob([data], { type: "audio/mpeg" }));
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
    line = addMessage("ai", "Người phỏng vấn", "");
    st.lines[turn] = line;
  }
  const el = line.querySelector(".bubble");
  el.textContent = el.textContent ? `${el.textContent} ${text}` : text;
  scrollChat();
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
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!st.holding) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    st.chunks = [];
    rec.ondataavailable = (e) => st.chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(st.chunks, { type: rec.mimeType });
      if (blob.size < 3000) {
        setStatus("Ghi âm quá ngắn. Hãy giữ nút lâu hơn.", "warn");
        return;
      }
      setStatus("Đang gửi…", "busy");
      st.ws.send(blob);
    };
    rec.start();
    st.rec = rec;
    $("#talk").classList.add("rec");
    $("#talk").setAttribute("aria-label", "Đang ghi âm, thả ra để gửi");
    setStatus("Đang ghi âm… thả ra để gửi", "recording");
  } catch (err) {
    st.holding = false;
    setStatus("Không mở được micro: " + err.message, "error");
  }
}

function stopRec() {
  st.holding = false;
  if (!st.rec) return;
  st.rec.stop();
  st.rec = null;
  $("#talk").classList.remove("rec");
  $("#talk").setAttribute("aria-label", "Giữ để nói");
}

const talk = $("#talk");
talk.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  startRec();
});
["pointerup", "pointerleave", "pointercancel"].forEach((ev) => talk.addEventListener(ev, stopRec));

// Hold Space to talk, unless the user is typing or using a form control.
const isTyping = () => ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
document.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.repeat || isTyping()) return;
  e.preventDefault();
  startRec();
});
document.addEventListener("keyup", (e) => {
  if (e.code !== "Space" || isTyping()) return;
  e.preventDefault();
  stopRec();
});

$("#typed").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || !e.target.value.trim()) return;
  stopPlayback();
  st.ws.send(JSON.stringify({ type: "text", text: e.target.value }));
  e.target.value = "";
});

init();
