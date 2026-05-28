import { useState, useEffect, useRef, useCallback } from "react";
import {
  api_list_campaigns,
  api_create_campaign,
  api_get_campaign,
  api_register_character,
  api_list_characters,
  api_start_session,
  api_end_session,
  api_get_session,
  api_send_message,
  api_get_messages,
  api_list_registries,
  api_load_from_registry,
  ws_connect,
  ws_send,
  type Campaign,
  type Character,
  type Message,
} from "./api";

// ── Views ──────────────────────────────────────────────────────────────────────

type View = "campaigns" | "registries" | "lobby" | "session";

export default function App() {
  const [view, setView] = useState<View>("campaigns");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [dm_token, setDm_token] = useState<string | null>(null);
  const [character_token, setCharacter_token] = useState<string | null>(null);
  const [character_name, setCharacter_name] = useState<string | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [session, setSession] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [msg_scope, setMsg_scope] = useState<"SINGLE" | "PARTY" | "BROADCAST">("SINGLE");
  const [msg_text, setMsg_text] = useState("");
  const [new_title, setNew_title] = useState("");
  const [new_char, setNew_char] = useState({ name: "", player_id: "", class: "", race: "" });
  const [error, setError] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const messages_end_ref = useRef<HTMLDivElement>(null);

  const is_dm = !!dm_token;

  // ── Campaign list ──────────────────────────────────────────────────────────

  const load_campaigns = useCallback(async () => {
    try {
      setCampaigns(await api_list_campaigns());
    } catch {}
  }, []);

  useEffect(() => { load_campaigns(); }, [load_campaigns]);

  // ── Join campaign ─────────────────────────────────────────────────────────

  async function handle_join(c: Campaign, as_dm: boolean, char_token?: string, char_name?: string) {
    try {
      const full = await api_get_campaign(c.id);
      setCampaign(full);
      if (as_dm) {
        setDm_token(char_token || dm_token || "");
        setCharacter_name(null);
      } else {
        setCharacter_token(char_token || "");
        setCharacter_name(char_name || null);
      }
      setView("lobby");
    } catch (e: any) { setError(e.message); }
  }

  async function handle_create() {
    if (!new_title.trim()) return;
    try {
      const c = await api_create_campaign(new_title.trim());
      setCampaign({ id: c.id, title: c.title, status: c.status });
      setDm_token(c.dm_token);
      setCharacter_name(null);
      setView("lobby");
    } catch (e: any) { setError(e.message); }
  }

  // ── Registry / Session Zero flow ─────────────────────────────────────────

  async function handle_browse_registries() {
    try {
      const regs = await api_list_registries();
      setView("registries");
    } catch (e: any) { setError(e.message); }
  }

  async function handle_load_from_registry(campaign_id: string) {
    try {
      const data = await api_load_from_registry(campaign_id);
      setCampaign({
        id: data.campaign.id,
        title: data.campaign.title,
        status: data.campaign.status,
        dm_token: data.campaign.dm_token,
        current_session: data.campaign.current_session,
        character_names: data.campaign.character_names,
      });
      setDm_token(data.campaign.dm_token);
      setCharacter_name(null);
      setView("lobby");
    } catch (e: any) { setError(e.message); }
  }

  // ── Lobby ─────────────────────────────────────────────────────────────────

  async function load_lobby() {
    if (!campaign) return;
    const [chars, sess] = await Promise.all([
      api_list_characters(campaign.id),
      api_get_session(campaign.id),
    ]);
    setCharacters(chars);
    setSession(sess);
  }

  useEffect(() => {
    if (view === "lobby" && campaign) load_lobby();
  }, [view, campaign]);

  async function handle_register_character() {
    if (!campaign || !dm_token || !new_char.name.trim() || !new_char.player_id.trim()) return;
    try {
      await api_register_character(campaign.id, dm_token, new_char);
      setNew_char({ name: "", player_id: "", class: "", race: "" });
      // Store character token for player — in a real app, player would get this via shareable link
      await load_lobby();
    } catch (e: any) { setError(e.message); }
  }

  async function handle_start_session() {
    if (!campaign || !dm_token) return;
    try {
      const s = await api_start_session(campaign.id, dm_token);
      setSession({ active: true, number: s.session_number, started_at: s.started_at });
    } catch (e: any) { setError(e.message); }
  }

  async function handle_end_session() {
    if (!campaign || !dm_token) return;
    try {
      await api_end_session(campaign.id, dm_token);
      setSession({ active: false });
    } catch (e: any) { setError(e.message); }
  }

  // ── Enter session ─────────────────────────────────────────────────────────

  async function handle_enter_session() {
    if (!campaign) return;
    const token = dm_token || character_token;
    const name = character_name;
    if (!token) return;

    try {
      const msgs = await api_get_messages(campaign.id, token);
      setMessages(msgs);

      // WebSocket connect
      const socket = ws_connect(
        campaign.id,
        token,
        name,
        dm_token,
        (data: any) => {
          if (data.type === "message") {
            setMessages((prev) => [...prev, data.payload as Message]);
          }
        },
      );
      setWs(socket);
      setView("session");
    } catch (e: any) { setError(e.message); }
  }

  // Auto-scroll messages
  useEffect(() => {
    messages_end_ref.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send message ────────────────────────────────────────────────────────────

  async function handle_send() {
    if (!campaign || !msg_text.trim()) return;
    const token = dm_token || character_token || "";
    try {
      await api_send_message(campaign.id, token, {
        content: msg_text.trim(),
        scope: msg_scope,
        recipient_names: msg_scope !== "BROADCAST" ? recipients : [],
      });
      setMsg_text("");
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws_send(ws, { type: "message", content: msg_text.trim(), scope: msg_scope, recipient_names: recipients });
      }
    } catch (e: any) { setError(e.message); }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div>
      {error && <div className="card" style={{borderLeft: "4px solid var(--accent)", color: "var(--accent)"}}>{error} <button onClick={() => setError("")} style={{marginLeft: 12}}>✕</button></div>}

      {view === "campaigns" && <CampaignsView
        campaigns={campaigns}
        new_title={new_title}
        setNew_title={setNew_title}
        on_create={handle_create}
        on_join={handle_join}
        on_browse_registries={handle_browse_registries}
        dm_token={dm_token}
        character_token={character_token}
        character_name={character_name}
      />}

      {view === "registries" && <RegistriesView
        on_select={handle_load_from_registry}
        on_back={() => setView("campaigns")}
      />}

      {view === "lobby" && <LobbyView
        campaign={campaign!}
        dm_token={dm_token!}
        is_dm={is_dm}
        characters={characters}
        session={session}
        new_char={new_char}
        setNew_char={setNew_char}
        on_register={handle_register_character}
        on_start={handle_start_session}
        on_end={handle_end_session}
        on_enter={handle_enter_session}
        on_back={() => setView("campaigns")}
      />}

      {view === "session" && <SessionView
        campaign={campaign!}
        is_dm={is_dm}
        messages={messages}
        msg_text={msg_text}
        setMsg_text={setMsg_text}
        msg_scope={msg_scope}
        setMsg_scope={setMsg_scope}
        recipients={recipients}
        setRecipients={setRecipients}
        characters={characters}
        on_send={handle_send}
        on_exit={() => { ws?.close(); setView("lobby"); }}
        messages_end_ref={messages_end_ref}
      />}
    </div>
  );
}

// ── Registry Picker (Session Zero — select a finalized campaign) ─────────────

function RegistriesView({ on_select, on_back }: any) {
  const [registries, setRegistries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api_list_registries()
      .then(setRegistries)
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20}}>
        <h2>Load Campaign</h2>
        <button onClick={on_back}>← Back</button>
      </div>

      <div className="card" style={{marginBottom: 20}}>
        <div className="label">Finalized Campaigns</div>
        <p style={{color: "var(--text-dim)", margin: "8px 0 12px"}}>
          Select a campaign whose Session Zero is complete. State is loaded into memory and the DM can begin.
        </p>
      </div>

      {loading && <p style={{color: "var(--text-dim)"}}>Loading...</p>}
      {error && <p style={{color: "var(--accent)"}}>{error}</p>}
      {!loading && registries.length === 0 && (
        <p style={{color: "var(--text-dim)"}}>No finalized campaigns found. Complete Session Zero in dnd-core first.</p>
      )}
      {registries.map((reg: any) => (
        <div key={reg.campaign_id} className="card">
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
            <div>
              <strong>{reg.campaign_id}</strong>
              <div style={{fontSize: 12, color: "var(--text-dim)", marginTop: 4}}>
                {reg.characters?.length ?? 0} characters · finalized {reg.session_zero_finalized_at ? new Date(reg.session_zero_finalized_at).toLocaleDateString() : "?"}
              </div>
            </div>
            <button onClick={() => on_select(reg.campaign_id)}>Load</button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Campaign List ──────────────────────────────────────────────────────────────

function CampaignsView({ campaigns, new_title, setNew_title, on_create, on_join, on_browse_registries, dm_token, character_token, character_name }: any) {
  return (
    <div>
      <h2 style={{marginBottom: 20}}> Campaigns</h2>
      <div className="card">
        <div className="field">
          <div className="label">New Campaign</div>
          <div style={{display: "flex", gap: 8}}>
            <input value={new_title} onChange={e => setNew_title(e.target.value)} placeholder="The Curse of Strahd" />
            <button onClick={on_create}>Create</button>
          </div>
        </div>
      </div>

      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", margin: "20px 0 10px"}}>
        <h3 style={{margin: 0}}>Active Campaigns</h3>
        <button onClick={on_browse_registries} style={{background: "var(--surface2)", fontSize: 13}}>
          Load from Registry →
        </button>
      </div>
      {campaigns.length === 0 && <p style={{color: "var(--text-dim)"}}>No campaigns yet.</p>}
      {campaigns.map((c: Campaign) => (
        <div key={c.id} className="card">
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
            <div>
              <strong>{c.title}</strong>
              <div style={{fontSize: 12, color: "var(--text-dim)", marginTop: 4}}>
                {c.status} · {c.id}
              </div>
            </div>
            <div style={{display: "flex", gap: 8}}>
              <button onClick={() => on_join(c, true)}>Join as DM</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Lobby ──────────────────────────────────────────────────────────────────────

function LobbyView({ campaign, dm_token, is_dm, characters, session, new_char, setNew_char, on_register, on_start, on_end, on_enter, on_back }: any) {
  return (
    <div>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20}}>
        <h2>{campaign.title}</h2>
        <button onClick={on_back}>← Back</button>
      </div>

      <div className="card">
        <div className="label">Session</div>
        {session?.active ? (
          <div>
            <span className="badge">Active — Session {session.number}</span>
            <div style={{marginTop: 8}}>
              <button onClick={on_enter}>Enter Session</button>
              {is_dm && <button onClick={on_end} style={{marginLeft: 8, background: "var(--surface2)"}}>End Session</button>}
            </div>
          </div>
        ) : (
          <div>
            <span style={{color: "var(--text-dim)"}}>No active session</span>
            {is_dm && <button onClick={on_start} style={{marginLeft: 12}}>Start Session {((session?.number) || 0) + 1}</button>}
          </div>
        )}
      </div>

      <div className="card">
        <div className="label">Characters</div>
        {characters.length === 0 && <p style={{color: "var(--text-dim)"}}>No characters registered.</p>}
        {characters.map((ch: Character) => (
          <div key={ch.name} style={{display: "flex", justifyContent: "space-between", marginBottom: 8}}>
            <span><strong>{ch.name}</strong> <span style={{color: "var(--text-dim)"}}>· {ch.race} {ch.class}</span></span>
            {session?.active && !is_dm && <button onClick={() => on_enter()}>Join</button>}
          </div>
        ))}

        {is_dm && (
          <div style={{marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 16}}>
            <div className="label" style={{marginBottom: 8}}>Register Character</div>
            <div className="split">
              <input placeholder="Name" value={new_char.name} onChange={e => setNew_char({...new_char, name: e.target.value})} />
              <input placeholder="Player ID" value={new_char.player_id} onChange={e => setNew_char({...new_char, player_id: e.target.value})} />
            </div>
            <div className="split" style={{marginTop: 8}}>
              <input placeholder="Class" value={new_char.class} onChange={e => setNew_char({...new_char, class: e.target.value})} />
              <input placeholder="Race" value={new_char.race} onChange={e => setNew_char({...new_char, race: e.target.value})} />
            </div>
            <button onClick={on_register} style={{marginTop: 10}}>Register</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Session ────────────────────────────────────────────────────────────────────

function SessionView({ campaign, is_dm, messages, msg_text, setMsg_text, msg_scope, setMsg_scope, recipients, setRecipients, characters, on_send, on_exit, messages_end_ref }: any) {
  return (
    <div>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16}}>
        <h2>{campaign.title} — Session</h2>
        <button onClick={on_exit} style={{background: "var(--surface2)"}}>Leave</button>
      </div>

      {/* Message feed */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        height: "55vh",
        overflowY: "auto",
        padding: "12px",
        marginBottom: 16,
      }}>
        {messages.length === 0 && <p style={{color: "var(--text-dim)", textAlign: "center", marginTop: 20}}>No messages yet.</p>}
        {messages.map((m: Message) => (
          <div key={m.id} style={{marginBottom: 12}}>
            <div style={{fontSize: 11, color: "var(--accent)"}}>
              {m.sender} {m.recipients?.length > 0 && `→ ${m.recipients.join(", ")}`}
              {m.scope === "BROADCAST" && " (broadcast)"}
              {m.is_system && " [system]"}
            </div>
            <div style={{fontSize: 14, marginTop: 2, whiteSpace: "pre-wrap"}}>{m.content}</div>
          </div>
        ))}
        <div ref={messages_end_ref} />
      </div>

      {/* Composer */}
      <div className="card" style={{marginBottom: 0}}>
        <div style={{display: "flex", gap: 8, marginBottom: 8}}>
          <select value={msg_scope} onChange={e => setMsg_scope(e.target.value as any)} style={{width: 120}}>
            <option value="SINGLE">To...</option>
            <option value="PARTY">Party</option>
            <option value="BROADCAST">All</option>
          </select>
          {msg_scope !== "BROADCAST" && (
            <input
              placeholder="Recipient names (comma-separated)"
              value={recipients.join(", ")}
              onChange={e => setRecipients(e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
            />
          )}
        </div>
        <div style={{display: "flex", gap: 8}}>
          <textarea
            value={msg_text}
            onChange={e => setMsg_text(e.target.value)}
            placeholder="Send a message..."
            rows={2}
            style={{flex: 1, resize: "none"}}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); on_send(); } }}
          />
          <button onClick={on_send} style={{height: "auto", alignSelf: "flex-end"}}>Send</button>
        </div>
      </div>
    </div>
  );
}