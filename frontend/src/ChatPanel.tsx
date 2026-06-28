import { useEffect, useRef, useState } from "react";
import { api, type ChatMessage, type ChatSession } from "./api";

export default function ChatPanel() {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .listChatSessions()
      .then((sessions) => {
        if (sessions.length) {
          setSession(sessions[0]);
        } else {
          return api.createChatSession().then(setSession);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!session) return;
    api.listChatMessages(session.id).then(setMessages).catch((e) => setError(String(e)));
  }, [session]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewSession = async () => {
    setError(null);
    const s = await api.createChatSession();
    setSession(s);
    setMessages([]);
  };

  const handleSend = async () => {
    if (!session || !input.trim() || sending) return;
    const content = input.trim();
    setInput("");
    setSending(true);
    setError(null);
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: "user", content, tool_calls: {}, created_at: new Date().toISOString() },
    ]);
    try {
      await api.postChatMessage(session.id, content);
      const fresh = await api.listChatMessages(session.id);
      setMessages(fresh);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setSending(false);
    }
  };

  const visibleMessages = messages.filter((m) => m.role === "user" || m.role === "assistant");

  return (
    <div className="chat-panel">
      <div className="chat-toolbar">
        <button onClick={handleNewSession}>New conversation</button>
      </div>
      <div className="chat-messages">
        {visibleMessages.length === 0 && (
          <p className="empty">
            Try: "What's our PCI score?", "Show open gaps", or "Let's integrate our Nessus
            scanner."
          </p>
        )}
        {visibleMessages.map((m) => (
          <div key={m.id} className={`chat-bubble chat-${m.role}`}>
            <div className="chat-role">{m.role === "user" ? "You" : "Assistant"}</div>
            <div className="chat-content">{m.content || <em>(no text — used a tool)</em>}</div>
          </div>
        ))}
        {sending && <div className="chat-bubble chat-assistant chat-pending">Thinking…</div>}
        <div ref={bottomRef} />
      </div>
      {error && <p className="error">{error}</p>}
      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          placeholder="Ask or instruct the GRC assistant..."
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={sending}
        />
        <button onClick={handleSend} disabled={sending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
