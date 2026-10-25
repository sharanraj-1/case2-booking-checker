// Minimal Streamlit custom-component protocol (v1): ready -> render(args) <-> setComponentValue.

type Listener = (args: Record<string, unknown>) => void;

function send(type: string, data: Record<string, unknown> = {}) {
  window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, "*");
}

export function connect(onRender: Listener): () => void {
  const handler = (e: MessageEvent) => {
    const d = e.data;
    if (d && d.type === "streamlit:render") onRender(d.args ?? {});
  };
  window.addEventListener("message", handler);
  send("streamlit:componentReady", { apiVersion: 1 });
  return () => window.removeEventListener("message", handler);
}

export function setValue(value: unknown) {
  send("streamlit:setComponentValue", { value, dataType: "json" });
}

export function setFrameHeight(height: number) {
  send("streamlit:setFrameHeight", { height });
}

let counter = 0;
export function eventId(): string {
  counter += 1;
  return `${Date.now().toString(36)}-${counter}-${Math.random().toString(36).slice(2, 7)}`;
}
