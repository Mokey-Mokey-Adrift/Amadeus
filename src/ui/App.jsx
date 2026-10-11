import { useEffect, useMemo, useRef, useState } from "react";
import logoUrl from "../../assets/images/latest.png";
import kurisuNeutral from "../../assets/character/kurisu-neutral.png";
import kurisuTalkOne from "../../assets/character/kurisu-talk-1.png";
import kurisuTalkTwo from "../../assets/character/kurisu-talk-2.png";

const api = window.amadeus;

const COPY = {
  ru: {
    newChat: "Новый чат", newKurisuChat: "Новый чат с Курису", newTitle: "Новое название чата",
    save: "Сохранить", cancel: "Отмена", chatActions: "Действия с чатом",
    rename: "Переименовать", delete: "Удалить", dismissMenu: "Закрыть меню",
    chatHistory: "История чатов", chatModes: "Режим чатов", assistant: "Ассистент",
    kurisu: "Курису", settings: "Настройки", hideChats: "Скрыть список чатов",
    showChats: "Показать список чатов", welcomeAssistant: "Я слушаю.",
    welcomeKurisu: "Я Курису.", beginAssistant: "Начните разговор или включите голосовой режим.",
    beginKurisu: "Начните разговор со мной.", you: "Вы", amadeus: "Амадэус",
    avatar: "Аватар персонажа", close: "Закрыть", message: "Сообщение",
    writeKurisu: "Напишите Курису...", writeAmadeus: "Напишите Амадэусу...",
    stopVoice: "Остановить голосовой режим", startVoice: "Включить голосовой режим",
    listening: "СЛУШАЮ", voice: "ГОЛОС", send: "Отправить",
    settingsTitle: "Настройки", language: "Язык", languageDescription: "Выберите язык интерфейса и ответов ассистента.",
    russian: "Русский", english: "Английский",
  },
  en: {
    newChat: "New chat", newKurisuChat: "New chat with Kurisu", newTitle: "New chat title",
    save: "Save", cancel: "Cancel", chatActions: "Chat actions",
    rename: "Rename", delete: "Delete", dismissMenu: "Close menu",
    chatHistory: "Chat history", chatModes: "Chat modes", assistant: "Assistant",
    kurisu: "Kurisu", settings: "Settings", hideChats: "Hide chat list",
    showChats: "Show chat list", welcomeAssistant: "I'm listening.",
    welcomeKurisu: "I'm Kurisu.", beginAssistant: "Start a conversation or enable voice mode.",
    beginKurisu: "Start a conversation with me.", you: "You", amadeus: "Amadeus",
    avatar: "Character avatar", close: "Close", message: "Message",
    writeKurisu: "Message Kurisu...", writeAmadeus: "Message Amadeus...",
    stopVoice: "Stop voice mode", startVoice: "Enable voice mode",
    listening: "LISTENING", voice: "VOICE", send: "Send",
    settingsTitle: "Settings", language: "Language", languageDescription: "Choose the interface and assistant response language.",
    russian: "Russian", english: "English",
  },
};

function text(language, key) {
  return COPY[language]?.[key] || COPY.ru[key] || key;
}

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };

  if (name === "plus") return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
  if (name === "more") return <svg {...common}><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></svg>;
  if (name === "send") return <svg {...common}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>;
  if (name === "mic") return <svg {...common}><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" /></svg>;
  if (name === "check") return <svg {...common}><path d="m5 12 4 4L19 6" /></svg>;
  if (name === "close") return <svg {...common}><path d="m18 6-12 12M6 6l12 12" /></svg>;
  if (name === "trash") return <svg {...common}><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6" /></svg>;
  if (name === "edit") return <svg {...common}><path d="m15 5 4 4M4 20l4-.8L19 8a2.1 2.1 0 0 0-3-3L5 16Z" /></svg>;
  if (name === "settings") return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1a1.7 1.7 0 1 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 1 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 1 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9H4a1.7 1.7 0 1 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 1 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 1 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 1 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 1 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z" /></svg>;
  return null;
}

function ChatRow({ chat, active, onSelect, onRename, onDelete, language }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(chat.title);
  const inputRef = useRef(null);

  useEffect(() => setTitle(chat.title), [chat.title]);
  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function saveTitle(event) {
    event.preventDefault();
    const next = title.trim();
    if (next) onRename(chat.id, next);
    setEditing(false);
  }

  if (editing) {
    return (
      <form className="chat-edit" onSubmit={saveTitle}>
        <input
          ref={inputRef}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          aria-label={text(language, "newTitle")}
        />
        <button className="icon-button confirm-button" type="submit" title={text(language, "save")}>
          <Icon name="check" size={16} />
        </button>
        <button
          className="icon-button"
          type="button"
          title={text(language, "cancel")}
          onClick={() => {
            setTitle(chat.title);
            setEditing(false);
          }}
        >
          <Icon name="close" size={16} />
        </button>
      </form>
    );
  }

  return (
    <div className={`chat-row ${active ? "active" : ""}`}>
      <button className="chat-select" onClick={() => onSelect(chat.id)} title={chat.title}>
        <span className="chat-indicator" />
        <span className="chat-title">{chat.title}</span>
      </button>
      <div className="chat-actions">
        <button
          className="icon-button more-button"
          title={text(language, "chatActions")}
          aria-label={`${text(language, "chatActions")}: ${chat.title}`}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <Icon name="more" />
        </button>
        {menuOpen && (
          <>
            <button className="menu-dismiss" aria-label={text(language, "dismissMenu")} onClick={() => setMenuOpen(false)} />
            <div className="chat-menu">
              <button onClick={() => { setMenuOpen(false); setEditing(true); }}>
                <Icon name="edit" size={15} /> {text(language, "rename")}
              </button>
              <button className="danger-action" onClick={() => { setMenuOpen(false); onDelete(chat.id); }}>
                <Icon name="trash" size={15} /> {text(language, "delete")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function KurisuAvatar({ processing, voiceActive, language }) {
  const [talkFrame, setTalkFrame] = useState(0);

  useEffect(() => {
    if (!processing) {
      setTalkFrame(0);
      return undefined;
    }

    const interval = window.setInterval(() => {
      setTalkFrame((frame) => (frame === 1 ? 2 : 1));
    }, 280);
    return () => window.clearInterval(interval);
  }, [processing]);

  const frame = processing
    ? [kurisuNeutral, kurisuTalkOne, kurisuTalkTwo][talkFrame]
    : kurisuNeutral;

  return (
    <div className={`character-avatar ${processing ? "is-speaking" : ""} ${voiceActive ? "is-listening" : ""}`}>
      <div className="character-glow" />
      <img src={frame} alt={language === "en" ? "Amadeus Kurisu avatar" : "Аватар Амадэуса Курису"} />
      <span className="character-name" aria-hidden="true" />
    </div>
  );
}

export default function App() {
  const [state, setState] = useState(null);
  const [chatMode, setChatMode] = useState("assistant");
  const [draft, setDraft] = useState("");
  const [processing, setProcessing] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [language, setLanguage] = useState("ru");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const visibleChats = useMemo(
    () => state?.chats?.filter((chat) => (chat.mode || "assistant") === chatMode) || [],
    [state, chatMode],
  );
  const activeChat = useMemo(
    () => visibleChats.find((chat) => chat.id === state?.active_chat_ids?.[chatMode])
      || visibleChats.find((chat) => chat.id === state?.active_chat_id)
      || visibleChats[0],
    [state, visibleChats, chatMode],
  );

  useEffect(() => {
    const unsubscribe = api.onEvent((message) => {
      if (message.event === "state") setState(message.state);
      if (message.event === "processing") setProcessing(message.active);
      if (message.event === "voice") setVoiceActive(message.active);
      if (message.event === "error") setError(message.message);
      if (message.event === "settings") setLanguage(message.settings.language);
    });
    api.command("get_state")
      .then(setState)
      .catch((commandError) => setError(commandError.message));
    api.command("get_settings")
      .then((settings) => setLanguage(settings.language))
      .catch((commandError) => setError(commandError.message));
    return unsubscribe;
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages, processing]);

  async function command(action, payload = {}) {
    setError("");
    try {
      return await api.command(action, payload);
    } catch (commandError) {
      setError(commandError.message);
      return undefined;
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || processing) return;
    setDraft("");
    await command("send_message", { text });
  }

  async function switchChatMode(nextMode) {
    const result = await command("activate_mode", { mode: nextMode });
    if (result) {
      setChatMode(nextMode);
      setSettingsOpen(false);
    }
  }

  async function changeLanguage(nextLanguage) {
    const result = await command("set_language", { language: nextLanguage });
    if (result) setLanguage(result.language);
  }

  function toggleChatMode() {
    const nextMode = chatMode === "assistant" ? "kurisu" : "assistant";
    void switchChatMode(nextMode);
  }

  return (
    <main className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"} ${chatMode === "assistant" ? "assistant-mode" : "kurisu-mode"}`}>
      {sidebarOpen && (
        <aside className="sidebar">
          <div className="sidebar-top">
            <div className="sidebar-heading">
              <img className="brand-logo" src={logoUrl} alt="Amadeus" />
              <button
                className="new-chat-button"
                onClick={() => { setSettingsOpen(false); void command("create_chat", { mode: chatMode }); }}
                title={chatMode === "kurisu" ? text(language, "newKurisuChat") : text(language, "newChat")}
              >
                <Icon name="plus" />
              </button>
            </div>
            <div className="sidebar-rule" />
          </div>
          <nav className="chat-list" aria-label={text(language, "chatHistory")}>
            {visibleChats.map((chat) => (
              <ChatRow
                key={chat.id}
                chat={chat}
                active={chat.id === activeChat?.id}
                onSelect={(chatId) => { setSettingsOpen(false); void command("switch_chat", { chat_id: chatId }); }}
                onRename={(chatId, title) => command("rename_chat", { chat_id: chatId, title })}
                onDelete={(chatId) => command("delete_chat", { chat_id: chatId })}
                language={language}
              />
            ))}
          </nav>
          <button
            className={`sidebar-settings-button ${settingsOpen ? "selected" : ""}`}
            aria-pressed={settingsOpen}
            onClick={() => setSettingsOpen((open) => !open)}
          >
            <Icon name="settings" size={16} />
            <span>{text(language, "settings")}</span>
          </button>
          <div className="chat-mode-switch" aria-label={text(language, "chatModes")}>
            <button
              className={chatMode === "assistant" ? "selected" : ""}
              aria-pressed={chatMode === "assistant"}
              onClick={toggleChatMode}
            >
              {text(language, "assistant")}
            </button>
            <button
              className={chatMode === "kurisu" ? "selected" : ""}
              aria-pressed={chatMode === "kurisu"}
              onClick={toggleChatMode}
            >
              {text(language, "kurisu")}
            </button>
          </div>
        </aside>
      )}

      <section className="workspace">
        <header className="topbar">
          <button
            className="icon-button sidebar-toggle"
            title={sidebarOpen ? text(language, "hideChats") : text(language, "showChats")}
            onClick={() => setSidebarOpen((open) => !open)}
          >
            <span className="toggle-glyph">{sidebarOpen ? "‹" : "☰"}</span>
          </button>
          <h2 className="topbar-title">{settingsOpen ? text(language, "settingsTitle") : activeChat?.title || "Amadeus"}</h2>
        </header>

        {settingsOpen ? (
          <section className="settings-view" aria-labelledby="settings-heading">
            <div className="settings-card">
              <div>
                <h1 id="settings-heading">{text(language, "language")}</h1>
                <p>{text(language, "languageDescription")}</p>
              </div>
              <div className="language-options" role="group" aria-label={text(language, "language")}>
                <button
                  className={language === "ru" ? "selected" : ""}
                  aria-pressed={language === "ru"}
                  onClick={() => void changeLanguage("ru")}
                >{text(language, "russian")}</button>
                <button
                  className={language === "en" ? "selected" : ""}
                  aria-pressed={language === "en"}
                  onClick={() => void changeLanguage("en")}
                >{text(language, "english")}</button>
              </div>
            </div>
          </section>
        ) : <div className="conversation">
          <div className="conversation-content">
            {!activeChat?.messages?.length ? (
              <div className="welcome">
                <h1>{chatMode === "kurisu" ? text(language, "welcomeKurisu") : text(language, "welcomeAssistant")}</h1>
                <p className="welcome-copy">
                  {chatMode === "kurisu" ? text(language, "beginKurisu") : text(language, "beginAssistant")}
                </p>
              </div>
            ) : (
              <div className="message-list">
                {activeChat.messages.map((message, index) => (
                  <article className={`message ${message.role}`} key={`${message.time || index}-${index}`}>
                    <div className="message-avatar">{message.role === "user" ? (language === "en" ? "YOU" : "ВЫ") : "A"}</div>
                    <div className="message-body">
                      <div className="message-author">{message.role === "user" ? text(language, "you") : text(language, "amadeus")}</div>
                      <p>{message.content}</p>
                    </div>
                  </article>
                ))}
                {processing && <div className="typing-indicator"><span /><span /><span /></div>}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
          {chatMode === "kurisu" && (
            <aside className="character-panel" aria-label={text(language, "avatar")}>
              <KurisuAvatar processing={processing} voiceActive={voiceActive} language={language} />
            </aside>
          )}
        </div>}

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button className="icon-button" onClick={() => setError("")} title={text(language, "close")}>
              <Icon name="close" size={16} />
            </button>
          </div>
        )}

        {!settingsOpen && <footer className="composer-wrap">
          <form className="composer" onSubmit={sendMessage}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form.requestSubmit();
                }
              }}
              placeholder={chatMode === "kurisu" ? text(language, "writeKurisu") : text(language, "writeAmadeus")}
              rows={1}
              aria-label={text(language, "message")}
            />
            <button
              className={`voice-button ${voiceActive ? "recording" : ""}`}
              type="button"
              onClick={() => command("toggle_voice")}
              title={voiceActive ? text(language, "stopVoice") : text(language, "startVoice")}
            >
              <Icon name="mic" size={17} />
              <span>{voiceActive ? text(language, "listening") : text(language, "voice")}</span>
            </button>
            <button className="send-button" type="submit" disabled={!draft.trim() || processing} title={text(language, "send")}>
              <Icon name="send" size={18} />
            </button>
          </form>
        </footer>}
      </section>
    </main>
  );
}
