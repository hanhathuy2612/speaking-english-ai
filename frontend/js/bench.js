const $ = (s) => document.querySelector(s);
let items = [],
  idx = 0,
  rec = null,
  holding = false,
  stream = null;

async function load() {
  items = await (await fetch("/api/bench")).json();
  const first = items.findIndex((x) => !x.done);
  idx = first < 0 ? 0 : first;
  render();
}

function render() {
  const ol = $("#list");
  ol.innerHTML = "";
  items.forEach((it, i) => {
    const li = document.createElement("li");
    li.textContent = it.text;
    li.className = (it.done ? "done " : "") + (i === idx ? "active" : "");
    li.onclick = () => {
      idx = i;
      render();
    };
    ol.appendChild(li);
  });
  const n = items.filter((x) => x.done).length;
  $("#current").textContent = items[idx]?.text || "";
  $("#status").textContent =
    n === items.length
      ? `Xong ${n}/${items.length} câu. Bạn có thể quay lại báo cho Claude.`
      : `Đã thu ${n}/${items.length} câu`;
}

async function start() {
  if (holding) return;
  holding = true;
  try {
    stream = stream || (await navigator.mediaDevices.getUserMedia({ audio: true }));
    if (!holding) return;
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "";
    const chunks = [];
    const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const i = idx;
    r.ondataavailable = (e) => chunks.push(e.data);
    r.onstop = async () => {
      const blob = new Blob(chunks, { type: r.mimeType });
      if (blob.size < 3000) {
        $("#status").textContent = "Thu quá ngắn, giữ nút lâu hơn.";
        return;
      }
      await fetch(`/api/bench/${i}`, { method: "POST", body: blob });
      items[i].done = true;
      const next = items.findIndex((x, k) => k > i && !x.done);
      idx = next >= 0 ? next : Math.min(i + 1, items.length - 1);
      render();
    };
    r.start();
    rec = r;
    $("#talk").classList.add("rec");
    $("#talk").textContent = "Đang thu. Thả ra để lưu";
  } catch (err) {
    holding = false;
    $("#status").textContent = "Không mở được micro: " + err.message;
  }
}

function stop() {
  holding = false;
  if (!rec) return;
  rec.stop();
  rec = null;
  $("#talk").classList.remove("rec");
  $("#talk").textContent = "Giữ để đọc";
}

const talk = $("#talk");
talk.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  start();
});
["pointerup", "pointerleave", "pointercancel"].forEach((ev) =>
  talk.addEventListener(ev, stop),
);
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && !e.repeat) {
    e.preventDefault();
    start();
  }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space") stop();
});
load();
