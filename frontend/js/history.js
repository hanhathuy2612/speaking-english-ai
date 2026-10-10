const $ = (s) => document.querySelector(s);
const SVG = "http://www.w3.org/2000/svg";

let sessions = [];

async function load() {
  const res = await (await fetch("/api/history/sessions")).json();
  sessions = res.sessions;
  if (!res.enabled) return showMessage("Lịch sử đang tắt (HISTORY_DB trong .env để trống).");
  if (!sessions.length) {
    return showMessage("Chưa có buổi tập nào. Hãy vào Phòng tập và trả lời vài câu, kết quả sẽ hiện ở đây.");
  }
  $("#message").hidden = true;
  $("#content").hidden = false;
  renderTiles();
  renderTable();
  requestAnimationFrame(renderCharts); // after #content is laid out, so charts know their width
}

function showMessage(text) {
  $("#message").textContent = text;
  $("#message").hidden = false;
  $("#content").hidden = true;
}

/* ---------- Formatting ---------- */
const pad = (n) => String(n).padStart(2, "0");
function fmtDate(iso, withTime = true) {
  const d = new Date(iso);
  const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  return withTime ? `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}
const fmtNum = (v) => (v == null ? "–" : String(v).replace(".", ","));

/* ---------- Stat tiles ---------- */
function renderTiles() {
  const box = $("#tiles");
  box.innerHTML = "";
  const tile = (label, value, unit, delta) => {
    const el = document.createElement("div");
    el.className = "card tile";
    el.innerHTML =
      '<div class="tile-label"></div><div class="tile-value"><span></span><span class="tile-unit"></span></div><div class="tile-delta"></div>';
    el.querySelector(".tile-label").textContent = label;
    el.querySelector(".tile-value span").textContent = value;
    el.querySelector(".tile-unit").textContent = unit;
    const d = el.querySelector(".tile-delta");
    d.textContent = delta?.text || "";
    if (delta?.tone) d.classList.add(delta.tone);
    box.appendChild(el);
  };

  const completed = sessions.filter((s) => s.completed).length;
  tile("Buổi tập", `${sessions.length}`, "", { text: `${completed} buổi hoàn thành đủ câu hỏi` });
  const spoken = sessions.reduce((a, s) => a + s.spoken_turns, 0);
  const words = sessions.reduce((a, s) => a + s.words, 0);
  tile("Lượt nói bằng giọng", `${spoken}`, "", { text: `${words} từ đã nói` });
  tile("Tốc độ khi nói, buổi gần nhất", ...latestWithDelta("wpm_speaking", "từ/phút", false));
  tile("Ngắt dài / 100 từ, buổi gần nhất", ...latestWithDelta("pauses_per_100_words", "", true));
}

// Latest value of a metric and its change vs the first session that has it.
function latestWithDelta(key, unit, lowerIsBetter) {
  const vals = sessions.filter((s) => s[key] != null);
  if (!vals.length) return ["–", unit, { text: "Chưa có lượt nói đủ dài để tính" }];
  const last = vals[vals.length - 1][key];
  if (vals.length < 2) return [fmtNum(last), unit, { text: "Cần ít nhất 2 buổi để so sánh" }];
  const diff = Math.round((last - vals[0][key]) * 10) / 10;
  const better = lowerIsBetter ? diff < 0 : diff > 0;
  const sign = diff > 0 ? "+" : diff < 0 ? "−" : "±";
  return [
    fmtNum(last),
    unit,
    { text: `${sign}${fmtNum(Math.abs(diff))} so với buổi đầu`, tone: diff === 0 ? "" : better ? "good" : "bad" },
  ];
}

/* ---------- Line charts ---------- */
function renderCharts() {
  lineChart($("#chartWpm"), "wpm_speaking", "từ/phút");
  lineChart($("#chartPauses"), "pauses_per_100_words", "lần / 100 từ");
}

function niceMax(v) {
  if (v <= 0) return 1;
  const step = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * step >= v) return m * step;
  return 10 * step;
}

function el(tag, attrs, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent?.appendChild(node);
  return node;
}

function lineChart(box, key, unit) {
  box.innerHTML = "";
  const pts = sessions.filter((s) => s[key] != null);
  if (!pts.length) {
    box.innerHTML = '<div class="chart-empty">Chưa có dữ liệu</div>';
    return;
  }
  const W = box.clientWidth;
  const H = box.clientHeight;
  if (W < 120) return; // not laid out yet; the ResizeObserver draws it once it has a size
  const m = { top: 12, right: 44, bottom: 26, left: 36 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  const maxV = niceMax(Math.max(...pts.map((p) => p[key])) * 1.1);
  const x = (i) => m.left + (pts.length === 1 ? iw / 2 : (i / (pts.length - 1)) * iw);
  const y = (v) => m.top + ih - (v / maxV) * ih;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Biểu đồ ${unit} theo buổi tập` }, box);

  // Recessive grid with 4 clean ticks from zero.
  for (let i = 0; i <= 4; i++) {
    const v = (maxV / 4) * i;
    el("line", { class: "grid", x1: m.left, x2: m.left + iw, y1: y(v), y2: y(v) }, svg);
    el("text", { class: "tick", x: m.left - 8, y: y(v) + 4, "text-anchor": "end" }, svg).textContent = fmtNum(
      Math.round(v * 10) / 10,
    );
  }
  // Sparse x labels: first, last and a few in between so they never collide.
  const every = Math.max(1, Math.ceil(pts.length / Math.max(1, Math.floor(iw / 70))));
  pts.forEach((p, i) => {
    if (i % every && i !== pts.length - 1) return;
    if (i !== pts.length - 1 && pts.length - 1 - i < every) return;
    el("text", { class: "tick", x: x(i), y: H - 6, "text-anchor": "middle" }, svg).textContent = fmtDate(
      p.started_at,
      false,
    );
  });

  const coords = pts.map((p, i) => [x(i), y(p[key])]);
  if (pts.length > 1) {
    const d = coords.map(([cx, cy], i) => `${i ? "L" : "M"}${cx},${cy}`).join(" ");
    el("path", { class: "area", d: `${d} L${coords.at(-1)[0]},${y(0)} L${coords[0][0]},${y(0)} Z` }, svg);
    el("path", { class: "line", d }, svg);
  }
  const dots = coords.map(([cx, cy]) => el("circle", { class: "point", cx, cy, r: 4 }, svg));
  // Direct label on the latest value only.
  const [lx, ly] = coords.at(-1);
  el("text", { class: "end-label", x: lx + 10, y: ly + 4 }, svg).textContent = fmtNum(pts.at(-1)[key]);

  // Crosshair + tooltip: snap to the nearest session along x.
  const cross = el("line", { class: "crosshair", y1: m.top, y2: m.top + ih, visibility: "hidden" }, svg);
  const hit = el("rect", { class: "hit", x: m.left - 10, y: m.top, width: iw + 20, height: ih }, svg);
  const tip = $("#tooltip");
  const hide = () => {
    cross.setAttribute("visibility", "hidden");
    dots.forEach((dot) => dot.classList.remove("active"));
    tip.hidden = true;
  };
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let i = 0;
    coords.forEach(([cx], k) => {
      if (Math.abs(cx - px) < Math.abs(coords[i][0] - px)) i = k;
    });
    cross.setAttribute("x1", coords[i][0]);
    cross.setAttribute("x2", coords[i][0]);
    cross.setAttribute("visibility", "visible");
    dots.forEach((dot, k) => dot.classList.toggle("active", k === i));
    tip.innerHTML = "<strong></strong><span></span>";
    tip.firstChild.textContent = `${fmtNum(pts[i][key])} ${unit}`;
    tip.lastChild.textContent = `${fmtDate(pts[i].started_at)} · ${pts[i].unit_title}`;
    tip.hidden = false;
    const left = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = `${left}px`;
    tip.style.top = `${e.clientY - tip.offsetHeight - 12}px`;
  });
  hit.addEventListener("pointerleave", hide);
}

/* ---------- Table (also the accessible view of the charts) ---------- */
function renderTable() {
  const body = $("#rows");
  body.innerHTML = "";
  [...sessions].reverse().forEach((s) => {
    const tr = document.createElement("tr");
    const cells = [
      [fmtDate(s.started_at), ""],
      [s.unit_title, ""],
      [`${s.spoken_turns}/${s.turns}`, "num"],
      [fmtNum(s.wpm_speaking), "num"],
      [fmtNum(s.pauses_per_100_words), "num"],
      [`${s.phrases_used}/${s.phrase_total}`, "num"],
    ];
    for (const [text, cls] of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      if (cls) td.className = cls;
      tr.appendChild(td);
    }
    const status = document.createElement("td");
    const chip = document.createElement("span");
    chip.className = s.completed ? "chip chip-success" : "chip";
    chip.textContent = s.completed ? "Hoàn thành" : "Dở dang";
    status.appendChild(chip);
    tr.appendChild(status);

    const del = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "btn btn-ghost";
    btn.setAttribute("aria-label", `Xóa buổi tập ${fmtDate(s.started_at)}`);
    btn.innerHTML =
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>';
    btn.onclick = async () => {
      if (!confirm(`Xóa buổi tập ${fmtDate(s.started_at)} (${s.unit_title})? Không thể hoàn tác.`)) return;
      await fetch(`/api/history/sessions/${s.id}`, { method: "DELETE" });
      load();
    };
    del.appendChild(btn);
    tr.appendChild(del);
    body.appendChild(tr);
  });
}

let resizeTimer;
new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => sessions.length && renderCharts(), 100);
}).observe(document.body);

load();
