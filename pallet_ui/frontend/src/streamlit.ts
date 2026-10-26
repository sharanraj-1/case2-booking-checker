// Transport to the Python side. Two modes, same events and payloads:
// - inside Streamlit: the Streamlit custom-component protocol (ready -> render(args) <-> setComponentValue);
// - standalone (e.g. on Vercel): POST /api/event with the session the browser keeps.

type Listener = (args: Record<string, unknown>) => void;

export const standalone = typeof window !== "undefined" && window.parent === window;
const API = "/api/event";
const KEY = "pallet-preflight-session";

let listener: Listener | null = null;
let session: unknown = null;
let lastPayload: Record<string, unknown> | null = null;
let queue: Promise<void> = Promise.resolve();

function send(type: string, data: Record<string, unknown> = {}) {
  window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, "*");
}

function loadSession(): unknown {
  try { const s = sessionStorage.getItem(KEY); return s ? JSON.parse(s) : null; } catch { return null; }
}

function saveSession(s: unknown) {
  try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode or full: keep it in memory only */ }
}

async function post(event: Record<string, unknown> | null) {
  const res = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session, event }) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const out = await res.json();
  session = out.session;
  saveSession(session);
  lastPayload = out.payload;
  listener?.({ payload: out.payload });
}

export function connect(onRender: Listener): () => void {
  listener = onRender;
  if (standalone) {
    session = loadSession();
    queue = queue.then(() => post(null)).catch(() => {
      session = null;  // a stale saved session: start fresh
      return post(null).catch(() => undefined);
    });
    return () => { listener = null; };
  }
  const handler = (e: MessageEvent) => {
    const d = e.data;
    if (d && d.type === "streamlit:render") onRender(d.args ?? {});
  };
  window.addEventListener("message", handler);
  send("streamlit:componentReady", { apiVersion: 1 });
  return () => window.removeEventListener("message", handler);
}

export function setValue(value: unknown) {
  if (!standalone) {
    send("streamlit:setComponentValue", { value, dataType: "json" });
    return;
  }
  const ev = value as Record<string, unknown>;
  queue = queue.then(() => post(ev)).catch(() => {
    // Tell the UI the request failed: same screen, the event acknowledged, a clear message.
    if (lastPayload) listener?.({ payload: { ...lastPayload, ack: ev.id, download: null,
      flash: "Couldn't reach the server just now. Please check your connection and try again." } });
  });
}

export function setFrameHeight(height: number) {
  if (!standalone) send("streamlit:setFrameHeight", { height });
}

/** Where to check the server is alive: Streamlit's health endpoint, or our API in standalone mode. */
export function healthUrl(): string {
  return standalone ? API : `${window.location.href.split("/component/")[0]}/_stcore/health`;
}

let counter = 0;
export function eventId(): string {
  counter += 1;
  return `${Date.now().toString(36)}-${counter}-${Math.random().toString(36).slice(2, 7)}`;
}
