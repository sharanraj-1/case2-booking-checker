// Shapes of the payload built by bridge.py. Keep in sync with bridge.payload().

export type Tone = "red" | "amber" | "green";
export type Severity = "Red" | "Data" | "Amber" | "Advisory";

export interface Option { value: string; label: string; hint: string; icon: string; suggested?: boolean }

export interface Ask {
  field: string;
  kind: "choice" | "number" | "date" | "text" | "item";
  question: string;
  hint?: string;
  options?: Option[];
  unit?: string;
  min?: number | string;
  step?: number;
  placeholder?: string;
  item_index?: number | null;
  missing?: string[];
  limit?: string | null;
  max?: number;
}

export interface Message { role: "user" | "assistant"; text: string; changes?: string[]; effects?: string[] }

export interface Row {
  key: string; label: string; display: string | null; raw: unknown; kind: "text" | "choice" | "date" | "number" | "stepper";
  options: string[] | null; missing: boolean; calculated: boolean; limit: string | null;
}

export interface Item {
  index: number; sku?: string; description?: string; hs_code?: string; qty?: number; unit_price?: number;
  units_per_carton?: number; cartons?: number; unit_kg?: number; coo?: string; calculated_cartons: boolean; missing: string[];
}

export interface Finding {
  rule: string; title: string; severity: Severity; message: string; fix: string; sku?: string | null;
  why?: string | null; action?: Record<string, unknown> | null; action_label?: string | null;
  ai?: { contains_dg: "yes" | "no" | "unsure"; category: string; why: string } | null; from_ai: boolean;
}

export interface CarrierOption {
  carrier: string; service: string; picked: boolean; eligible: boolean | null; cost: number | null; cost_label: string;
  per_pallet: string; transit: number; on_time: number; max_kg: number; eta: string | null; excluded: string | null;
}

export interface Result {
  id: string; status: string;
  view: { tone: Tone; label: string; headline: string; sub: string };
  counts: { red: number; data: number; amber: number; advisory: number; passed: number };
  rules: { id: string; name: string; state: "Pass" | "Red" | "Amber" | "Data"; why: string }[];
  findings: Finding[]; options: CarrierOption[]; recommendation: string | null; reason: string; why_others: string[];
  load: { gross: string | null; pallets: string | null; per_pallet: string | null; priority: string };
  confirmation: {
    blocked: boolean; route: string; seller: string; carrier: string | null; cost: string | null; cost_detail: string;
    collection: string | null; eta: string | null; eta_notes: string; goods: string; todo: string[];
  };
  next_steps: { title: string; body: string; link?: string; link_label?: string }[];
  notices: string[];
  invoice: { rows: { n: number; title: string; state: "ready" | "check" | "add" | "info"; detail: string }[];
    counts: Record<string, number>; source: string };
  country: { country: string; export: string[]; import: string[]; statement_on_origin: string | null; sources: string[] } | null;
  live: LiveView | null;
  can_live: boolean;
}

export interface LiveQuote { service: string; price: number; transit: string | null; mode: string }
export interface LiveView {
  ok: boolean; error: string | null; quotes: LiveQuote[]; pallet_type?: string; fetched_at?: string; source?: string;
  ours?: { carrier: string; cost: number; cost_label: string }; summary?: string;
}

export interface ChatView {
  messages: Message[]; ask: Ask | null; rows: Row[]; items: Item[];
  progress: { done: number; total: number }; complete: boolean; confirmed: boolean; result: Result | null;
}

export interface FileRow {
  id: string; seller: string; route: string; status: string; tone: Tone; label: string; problems: number;
  warnings: number; carrier: string | null; cost: string; eta: string; edited: boolean;
}

export interface FileView {
  label: string; notices: { level: string; message: string }[];
  counts: { total: number; Blocked: number; "Ready with warnings": number; Ready: number };
  rows: FileRow[]; results: Record<string, Result>; xlsx: string | null;
}

export interface Payload {
  ack: string | null; ai: boolean; today: string; flash: string | null; chat: ChatView; file: FileView | null;
  download: { id: string; name: string; b64: string } | null;
  coo_options: string[]; item_fields: Record<string, [string, string, string, string]>; tariff_link: string;
  limits: Limits;
}

export interface Limits {
  per_pallet: Record<string, number>; top_kg: number; seller_max: number; description_max: number; hs_max: number;
  message_max: number; upload_mb: number; live_max_pallets: number; live_max_kg: number;
}

export type UIEvent = Record<string, unknown> & { type: string };
export type Send = (ev: UIEvent) => void;
