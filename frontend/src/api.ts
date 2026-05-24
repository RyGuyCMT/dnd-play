// D&D Play — API client & WebSocket hook

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface Campaign {
  id: string;
  title: string;
  status: string;
  dm_token?: string;
  current_session?: number | null;
  character_names?: string[];
}

export interface Character {
  name: string;
  player_id: string;
  class: string;
  race: string;
}

export interface Message {
  id: string;
  sender: string;
  recipients: string[];
  scope: string;
  content: string;
  sent_at: string;
  session_number?: number | null;
  is_system: boolean;
}

// ── REST API ──────────────────────────────────────────────────────────────────

async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// Campaigns
export const api_create_campaign = (title: string) =>
  api("/campaigns", { method: "POST", body: JSON.stringify({ title }) });

export const api_list_campaigns = () => api("/campaigns");

export const api_get_campaign = (id: string) =>
  api(`/campaigns/${id}`);

// Sessions
export const api_start_session = (campaign_id: string, token: string) =>
  api(`/campaigns/${campaign_id}/sessions/start`, {
    headers: { Authorization: `Bearer ${token}` },
  });

export const api_end_session = (campaign_id: string, token: string) =>
  api(`/campaigns/${campaign_id}/sessions/end`, {
    headers: { Authorization: `Bearer ${token}` },
  });

export const api_get_session = (campaign_id: string) =>
  api(`/campaigns/${campaign_id}/sessions`);

// Characters
export const api_register_character = (
  campaign_id: string,
  token: string,
  data: { name: string; player_id: string; class?: string; race?: string },
) =>
  api(`/campaigns/${campaign_id}/characters`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });

export const api_list_characters = (campaign_id: string) =>
  api(`/campaigns/${campaign_id}/characters`);

export const api_connect_character = (
  campaign_id: string,
  character_name: string,
  token: string,
) =>
  api(`/campaigns/${campaign_id}/sessions/characters/${character_name}/connect`, {
    headers: { Authorization: `Bearer ${token}` },
  });

// Messages
export const api_send_message = (
  campaign_id: string,
  token: string,
  data: { content: string; scope?: string; recipient_names?: string[] },
) =>
  api(`/campaigns/${campaign_id}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });

export const api_get_messages = (campaign_id: string, token: string) =>
  api(`/campaigns/${campaign_id}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  });

// ── WebSocket ────────────────────────────────────────────────────────────────

type WsHandler = (msg: Message | { type: string; payload: any }) => void;

export function ws_connect(
  campaign_id: string,
  token: string,
  character_name: string | null,
  _dm_token: string | null,
  on_message: WsHandler,
) {
  const params = new URLSearchParams({ token });
  if (character_name) params.set("character_name", character_name);
  const ws = new WebSocket(`${BASE.replace("http", "ws")}/campaigns/${campaign_id}/ws?${params}`);

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    on_message(data);
  };

  ws.onerror = () => ws.close();

  return ws;
}

export function ws_send(ws: WebSocket, payload: object) {
  ws.send(JSON.stringify(payload));
}