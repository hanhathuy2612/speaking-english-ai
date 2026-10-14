import { useCallback, useEffect, useReducer, useRef } from "react";
import type {
  AnswerStep,
  ClientMessage,
  Metrics,
  RetellResult,
  ServerMessage,
  SessionSummary,
  ShadowResult,
  Speech,
  UnitInfo,
  UnclearReason,
  Topic,
  UnitsResponse,
} from "../../api/types";
import { api, AUTH_EXPIRED } from "../../api/http";
import type { Status } from "../../components/ui";
import { useAudioQueue } from "../../hooks/useAudioQueue";
import { useRecordings } from "../../hooks/useRecordings";
import type { WithAudio } from "../../lib/replay";
import { pickUnit } from "../../lib/roadmap";

export type ChatItem =
  | { id: number; kind: "ai"; turn: number; text: string }
  | {
      id: number;
      kind: "me";
      turn: number;
      text: string;
      speech: Speech;
      unclear: UnclearReason | null;
      audio?: string; // object URL of the recording, for "Nghe lại" (spoken answers only)
    }
  | { id: number; kind: "summary"; summary: SessionSummary };

export type InterviewState = {
  topics: Topic[];
  unitId: string;
  unit: UnitInfo | null;
  items: ChatItem[];
  used: number[];
  progress: { q: number; n: number; done: boolean } | null;
  coach: { text: string; retry: boolean; steps: AnswerStep[] } | null;
  shadow: { waiting: boolean; result: WithAudio<ShadowResult> | null };
  retell: { waiting: boolean; result: WithAudio<RetellResult> | null }; // "Trả lời lại dài hơn"
  metrics: Metrics;
  conf: number | null;
  status: Status;
  canUndo: boolean;
  turn: number;
  lastMeTurn: number | null; // turn of the last accepted answer, removed on undo
};

const initial: InterviewState = {
  topics: [],
  unitId: "",
  unit: null,
  items: [],
  used: [],
  progress: null,
  coach: null,
  shadow: { waiting: false, result: null },
  retell: { waiting: false, result: null },
  metrics: {},
  conf: null,
  status: { text: "", state: "" },
  canUndo: false,
  turn: 0,
  lastMeTurn: null,
};

type Action =
  | { type: "topics"; topics: Topic[] }
  | { type: "select"; unitId: string }
  | { type: "server"; msg: ServerMessage; audio?: string }
  | { type: "aiSentence"; turn: number; text: string }
  | { type: "status"; status: Status }
  | { type: "shadowWaiting"; waiting: boolean }
  | { type: "retellWaiting"; waiting: boolean };

let nextId = 1;
const noShadow = { waiting: false, result: null };
const noRetell = { waiting: false, result: null };

function reducer(s: InterviewState, a: Action): InterviewState {
  switch (a.type) {
    case "topics":
      return { ...s, topics: a.topics };
    case "select":
      return { ...s, unitId: a.unitId };
    case "status":
      return { ...s, status: a.status };
    case "shadowWaiting":
      return { ...s, shadow: { ...s.shadow, waiting: a.waiting } };
    case "retellWaiting":
      return { ...s, retell: { ...s.retell, waiting: a.waiting } };
    case "aiSentence": {
      // The interviewer's text appears sentence by sentence as the audio starts playing.
      const i = s.items.findIndex((it) => it.kind === "ai" && it.turn === a.turn);
      if (i < 0) return { ...s, items: [...s.items, { id: nextId++, kind: "ai", turn: a.turn, text: a.text }] };
      const items = [...s.items];
      const it = items[i] as Extract<ChatItem, { kind: "ai" }>;
      items[i] = { ...it, text: `${it.text} ${a.text}` };
      return { ...s, items };
    }
    case "server":
      return onServer(s, a.msg, a.audio);
  }
}

/** `audio`: object URL of the recording a transcript, shadow_result or retell_result came from. */
function onServer(s: InterviewState, m: ServerMessage, audio?: string): InterviewState {
  switch (m.type) {
    case "started":
      return {
        ...s,
        unit: m.unit,
        items: [],
        used: [],
        coach: null,
        shadow: noShadow,
        retell: noRetell,
        canUndo: false,
        turn: 0,
        lastMeTurn: null,
      };
    case "status":
      return {
        ...s,
        status: { text: m.msg === "transcribing" ? "Đang nhận dạng giọng nói…" : "AI đang trả lời…", state: "busy" },
      };
    case "transcript": {
      const turn = s.turn + 1;
      const me = { id: nextId++, kind: "me" as const, turn, text: m.text, speech: m.speech, unclear: m.reason, audio };
      if (m.unclear) {
        return {
          ...s,
          turn,
          items: [...s.items, me],
          conf: m.conf,
          canUndo: false,
          status: {
            text: m.reason === "not_english" ? "Hãy trả lời bằng tiếng Anh nhé." : "Máy nghe chưa rõ, bạn nói lại nhé.",
            state: "warn",
          },
        };
      }
      return {
        ...s,
        turn,
        lastMeTurn: turn,
        items: [...s.items, me],
        used: m.used,
        conf: m.conf,
        canUndo: false,
        coach: null,
        shadow: noShadow,
        retell: noRetell,
      };
    }
    case "undone":
      return {
        ...s,
        items: s.items.filter(
          (it) => it.kind !== "summary" && !("turn" in it && it.turn === s.lastMeTurn && s.lastMeTurn !== null),
        ),
        lastMeTurn: null,
        used: m.used,
        coach: null,
        shadow: noShadow,
        retell: noRetell,
        status: { text: "Đã bỏ lượt vừa rồi. Hãy trả lời lại.", state: "ready" },
      };
    case "progress":
      return { ...s, progress: { q: m.q, n: m.n, done: m.done } };
    case "summary": {
      const { type: _type, ...summary } = m;
      return {
        ...s,
        items: [...s.items.filter((it) => it.kind !== "summary"), { id: nextId++, kind: "summary", summary }],
      };
    }
    case "note":
      return m.text
        ? { ...s, coach: { text: m.text, retry: m.retry, steps: m.steps ?? [] }, shadow: noShadow, retell: noRetell }
        : s;
    case "shadow_result": {
      const { type: _type, ...result } = m;
      return { ...s, shadow: { waiting: false, result: { ...result, audio } } };
    }
    case "retell_result": {
      const { type: _type, ...result } = m;
      return { ...s, retell: { waiting: false, result: { ...result, audio } } };
    }
    case "metrics": {
      const { type: _type, ...metrics } = m;
      return { ...s, metrics };
    }
    case "turn_done":
      return {
        ...s,
        canUndo: !!m.can_undo,
        status: s.status.state === "warn" ? s.status : { text: "Sẵn sàng, mời bạn trả lời", state: "ready" },
      };
    case "error":
      return { ...s, status: { text: `Lỗi: ${m.msg}`, state: "error" } };
    case "sentence":
      return s; // paired with the next binary frame, handled outside the reducer
  }
}

type AudioMeta = { text: string; role: "ai" | "model"; turn: number };

/** WebSocket session with the interview backend: protocol state, audio playback and actions. */
export function useInterview(requestedUnit: string | null) {
  const [state, dispatch] = useReducer(reducer, initial);
  const ws = useRef<WebSocket | null>(null);
  const pending = useRef<AudioMeta | null>(null);
  // Mirrors state.turn but is updated synchronously per message, because audio frames of a turn
  // can arrive before React re-renders.
  const turnRef = useRef(0);
  const keepRecording = useRecordings();
  const lastRecording = useRef<string | null>(null); // recording waiting for its transcript

  const audio = useAudioQueue<AudioMeta>((meta) => {
    if (meta.role === "ai") dispatch({ type: "aiSentence", turn: meta.turn, text: meta.text });
  });

  const send = useCallback((msg: ClientMessage | Blob) => {
    const sock = ws.current;
    if (!sock || sock.readyState !== WebSocket.OPEN) return;
    sock.send(msg instanceof Blob ? msg : JSON.stringify(msg));
  }, []);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const sock = new WebSocket(`${proto}://${location.host}/ws`);
    ws.current = sock;
    let closedByUs = false;
    sock.onopen = async () => {
      const { topics, next_unit } = await api<UnitsResponse>("/api/units");
      dispatch({ type: "topics", topics });
      const first = pickUnit(topics, requestedUnit, next_unit);
      if (first) {
        dispatch({ type: "select", unitId: first });
        dispatch({ type: "status", status: { text: "Đang chuẩn bị bài…", state: "busy" } });
        sock.send(JSON.stringify({ type: "start", unit: first }));
      }
    };
    sock.onclose = (e) => {
      if (e.code === 4401)
        window.dispatchEvent(new Event(AUTH_EXPIRED)); // login gone: back to /login
      else if (!closedByUs)
        dispatch({
          type: "status",
          status: { text: "Mất kết nối với máy chủ. Tải lại trang để thử lại.", state: "error" },
        });
    };
    sock.onmessage = (e) => {
      if (typeof e.data !== "string") {
        // binary frame = MP3 for the sentence announced just before
        if (pending.current) audio.enqueue(pending.current, e.data as Blob);
        pending.current = null;
        return;
      }
      const msg = JSON.parse(e.data) as ServerMessage;
      if (msg.type === "sentence") {
        pending.current = { text: msg.text, role: msg.role, turn: turnRef.current };
        return;
      }
      if (msg.type === "started") turnRef.current = 0;
      if (msg.type === "transcript") turnRef.current += 1;
      if (msg.type === "transcript" || msg.type === "shadow_result" || msg.type === "retell_result") {
        // The answer to the recording sent last: keep it for "Nghe lại".
        dispatch({ type: "server", msg, audio: lastRecording.current ?? undefined });
        lastRecording.current = null;
        return;
      }
      dispatch({ type: "server", msg });
    };
    return () => {
      closedByUs = true;
      sock.close();
    };
  }, [audio.enqueue]); // requestedUnit is only read when the socket opens; switching units uses startUnit

  const startUnit = useCallback(
    (unitId: string) => {
      audio.stop();
      dispatch({ type: "select", unitId });
      dispatch({ type: "status", status: { text: "Đang chuẩn bị bài…", state: "busy" } });
      send({ type: "start", unit: unitId });
    },
    [audio, send],
  );

  const sendText = useCallback(
    (text: string) => {
      audio.stop();
      dispatch({ type: "shadowWaiting", waiting: false }); // a typed message is always an interview answer
      dispatch({ type: "retellWaiting", waiting: false });
      lastRecording.current = null;
      send({ type: "text", text });
    },
    [audio, send],
  );

  /** A shadowing or retell attempt is announced right before its audio, so the server neither
   * treats it as a new answer nor moves on. */
  const sendRecording = useCallback(
    (blob: Blob) => {
      dispatch({ type: "status", status: { text: "Đang gửi…", state: "busy" } });
      lastRecording.current = keepRecording(blob);
      if (state.shadow.waiting && state.coach) send({ type: "shadow", text: state.coach.text });
      else if (state.retell.waiting) send({ type: "retell" });
      send(blob);
    },
    [send, state.shadow.waiting, state.retell.waiting, state.coach, keepRecording],
  );

  const ready = () => dispatch({ type: "status", status: { text: "Sẵn sàng, mời bạn trả lời", state: "ready" } });

  const actions = {
    startUnit,
    sendText,
    sendRecording,
    stopAudio: audio.stop,
    undo: () => send({ type: "undo" }),
    playNote: (text: string) => send({ type: "say_it", text }),
    setStatus: (status: Status) => dispatch({ type: "status", status }),
    beginShadow: () => {
      dispatch({ type: "retellWaiting", waiting: false });
      dispatch({ type: "shadowWaiting", waiting: true });
      dispatch({ type: "status", status: { text: "Đang mở micro, đọc câu mẫu khi nút chuyển đỏ", state: "ready" } });
    },
    cancelShadow: () => {
      dispatch({ type: "shadowWaiting", waiting: false });
      ready();
    },
    beginRetell: () => {
      dispatch({ type: "shadowWaiting", waiting: false });
      dispatch({ type: "retellWaiting", waiting: true });
      dispatch({
        type: "status",
        status: { text: "Đang mở micro, trả lời lại và thêm các ý gợi ý khi nút chuyển đỏ", state: "ready" },
      });
    },
    cancelRetell: () => {
      dispatch({ type: "retellWaiting", waiting: false });
      ready();
    },
  };

  return { state, actions };
}
