
import { useEffect, useState } from "react";
import {
  BrainCircuit,
  MessageSquareText,
  Files,
  ShieldCheck,
  Activity,
  Settings,
  Sun,
  Moon,
  Plus,
  Search,
  ArrowUp,
  Paperclip,
  Sparkles,
  FileText,
  ChevronDown,
  Menu,
  X,
  LockKeyhole,
  ChartNoAxesCombined,
  Zap,
} from "lucide-react";

import "./App.css";
import KnowledgeBase from "./KnowledgeBase";
import SecurityActivity from "./SecurityActivity";
import Workplace from "./Workplace";
import SettingsPage from "./Settings";
import Login from "./Login";
import Evaluation from "./Evaluation";
import Observability from "./Observability";

function getApiBaseUrl() {
  const frontendHost = window.location.hostname;
  const configuredUrl =
    import.meta.env.VITE_API_BASE_URL ||
    `http://${frontendHost}:8000`;

  const apiUrl = new URL(configuredUrl);

  if (
    ["localhost", "127.0.0.1"].includes(frontendHost) &&
    ["localhost", "127.0.0.1"].includes(apiUrl.hostname)
  ) {
    apiUrl.hostname = frontendHost;
  }

  return apiUrl.origin;
}

const API_BASE_URL = getApiBaseUrl();

const THEMES = [
  { id: "light", label: "Light" },
  { id: "midnight", label: "Midnight Blue" },
  { id: "emerald", label: "Emerald" },
  { id: "amethyst", label: "Amethyst" },
];

function getSavedTheme() {
  try {
    const savedTheme = localStorage.getItem(
      "knowledge-copilot-theme"
    );

    return THEMES.some((theme) => theme.id === savedTheme)
      ? savedTheme
      : "light";
  } catch {
    return "light";
  }
}

function getCsrfToken() {
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith("kc_csrf="));

  if (!cookie) return "";

  const value = cookie.substring("kc_csrf=".length);

  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const suggestions = [
  {
    title: "Understand a policy",
    description: "Summarize a company policy in simple language.",
    icon: ShieldCheck,
    prompt: "Explain the production database access policy.",
  },
  {
    title: "Find an answer",
    description: "Find information across authorized documents.",
    icon: Search,
    prompt:
      "What approval is required before accessing the production database?",
  },
  {
    title: "Review a document",
    description: "Get a quick overview of important information.",
    icon: FileText,
    prompt: "Summarize the key points in the security policy.",
  },
];

async function askBackend(question, topK = 3, modelProfile = "standard") {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/ask`, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify({
        question,
        top_k: topK,
        model_profile: modelProfile,
      }),
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Check that FastAPI is running at " +
      API_BASE_URL
    );
  }

  if (!response.ok) {
    let detail = "";

    try {
      const errorBody = await response.json();
      detail =
        typeof errorBody.detail === "string" ? errorBody.detail : "";
    } catch {
      // The server may not return a JSON error body.
    }

    if (response.status === 401) {
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (response.status === 403) {
      throw new Error(
        detail || "Your request failed the security check."
      );
    }

    if (response.status === 422) {
      throw new Error(
        detail ||
        "The question was rejected. Check its length and parameters."
      );
    }

    if (response.status === 503) {
      throw new Error(
        "The question service is temporarily unavailable. Check that Ollama and the required model are running."
      );
    }

    throw new Error(
      detail || `The backend returned HTTP ${response.status}.`
    );
  }

  return response.json();
}

async function askBackendStream(question, topK = 3, onChunk, onSources, modelProfile = "standard") {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/ask/stream`, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "X-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify({
        question,
        top_k: topK,
        model_profile: modelProfile,
      }),
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Check that FastAPI is running at " +
      API_BASE_URL
    );
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    if (response.status === 403) {
      throw new Error("Your request failed the security check.");
    }
    throw new Error(`The assistant failed to respond (HTTP ${response.status}).`);
  }

  if (!response.body) {
    return await askBackend(question, topK);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let accumulatedAnswer = "";
  let finalResult = null;
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const trimmed = block.trim();
      if (!trimmed) continue;

      let eventType = "message";
      let dataText = "";

      for (const line of trimmed.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.substring(6).trim();
        } else if (line.startsWith("data:")) {
          dataText = line.substring(5).trim();
        }
      }

      if (!dataText) continue;

      try {
        const parsed = JSON.parse(dataText);
        if (eventType === "start" || parsed.event === "start") {
          if (Array.isArray(parsed.sources) && onSources) {
            onSources(parsed.sources);
          }
        } else if (eventType === "token" || parsed.event === "token") {
          const token = parsed.token || "";
          accumulatedAnswer += token;
          if (onChunk) {
            onChunk(accumulatedAnswer);
          }
        } else if (eventType === "done" || parsed.event === "done") {
          finalResult = parsed;
        } else if (eventType === "error" || parsed.event === "error") {
          throw new Error(parsed.error || "Streaming generation error.");
        }
      } catch (err) {
        if (err instanceof Error && err.message.includes("Streaming generation error")) {
          throw err;
        }
      }
    }
  }

  if (finalResult) {
    return finalResult;
  }

  return {
    answer: accumulatedAnswer,
    clean_answer: accumulatedAnswer,
    abstained: accumulatedAnswer.length === 0,
    sources: [],
    confidence_score: null,
  };
}

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

function App() {
  const [authStatus, setAuthStatus] = useState("checking");
  const [currentUser, setCurrentUser] = useState(null);
  const [authError, setAuthError] = useState("");

  const [theme, setTheme] = useState(getSavedTheme);

  const [activePage, setActivePage] = useState("AI Assistant");
  const [modelProfile, setModelProfile] = useState(() => {
    try {
      return localStorage.getItem("rag_model_profile") || "standard";
    } catch {
      return "standard";
    }
  });

  function handleModelProfileChange(profile) {
    setModelProfile(profile);
    try {
      localStorage.setItem("rag_model_profile", profile);
    } catch {
      // Ignore localStorage errors
    }
  }

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showNotice, setShowNotice] = useState(true);
  const [chatError, setChatError] = useState("");

  // Persist the selected theme and apply the matching root class.
  useEffect(() => {
    try {
      localStorage.setItem("knowledge-copilot-theme", theme);
    } catch {
      // Theme selection still works for the current session.
    }

    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme =
      theme === "light" ? "light" : "dark";
  }, [theme]);

  // Verify the existing cookie-based session.
  useEffect(() => {
    let cancelled = false;

    async function checkSession() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/auth/me`,
          {
            method: "GET",
            credentials: "include",
            headers: {
              Accept: "application/json",
            },
          }
        );

        if (!response.ok) {
          if (response.status !== 401) {
            throw new Error(
              `Session check failed (HTTP ${response.status}).`
            );
          }

          if (!cancelled) {
            setCurrentUser(null);
            setAuthStatus("signed-out");
          }

          return;
        }

        const user = await response.json();

        if (!cancelled) {
          setCurrentUser(user);
          setAuthStatus("signed-in");
        }
      } catch {
        if (!cancelled) {
          setAuthError(
            "Unable to verify your session. Check that the backend is running."
          );
          setAuthStatus("error");
        }
      }
    }

    checkSession();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleLogin(user) {
    setCurrentUser(user);
    setAuthError("");
    setAuthStatus("signed-in");
  }

  async function handleLogout() {
    setAuthError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/auth/logout`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            Accept: "application/json",
            "X-CSRF-Token": getCsrfToken(),
          },
        }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));

        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : `Logout failed (HTTP ${response.status}).`
        );
      }

      setCurrentUser(null);
      setMessages([]);
      setQuestion("");
      setChatError("");
      setActivePage("AI Assistant");
      setAuthStatus("signed-out");
    } catch (error) {
      setAuthError(
        error instanceof Error
          ? error.message
          : "Unable to log out. Please try again."
      );
    }
  }

  async function submitQuestion(value = question) {
    const text = value.trim();

    if (!text || loading) return;

    const messageId = createMessageId();

    setMessages((previous) => [
      ...previous,
      {
        id: messageId,
        question: text,
        status: "loading",
        answer: "",
        abstained: false,
        sources: [],
        error: "",
      },
    ]);

    setQuestion("");
    setChatError("");
    setActivePage("AI Assistant");
    setSidebarOpen(false);
    setLoading(true);

    try {
      const result = await askBackendStream(
        text,
        3,
        (partialText) => {
          setMessages((previous) =>
            previous.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    answer: partialText,
                    status: "loading",
                  }
                : message
            )
          );
        },
        (previewSources) => {
          setMessages((previous) =>
            previous.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    sources: previewSources,
                  }
                : message
            )
          );
        },
        modelProfile
      );

      setMessages((previous) =>
        previous.map((message) =>
          message.id === messageId
            ? {
              ...message,
              status: "success",
              answer: result.clean_answer || result.answer,
              rawAnswer: result.answer,
              abstained: result.abstained,
              confidenceScore: typeof result.confidence_score === "number" ? result.confidence_score : null,
              model: result.model,
              sources: Array.isArray(result.sources)
                ? result.sources
                : [],
            }
            : message
        )
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "An unexpected error occurred.";

      setChatError(errorMessage);

      setMessages((previous) =>
        previous.map((message) =>
          message.id === messageId
            ? {
              ...message,
              status: "error",
              error: errorMessage,
            }
            : message
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    setMessages([]);
    setQuestion("");
    setChatError("");
    setLoading(false);
    setActivePage("AI Assistant");
    setSidebarOpen(false);
  }

  function selectPage(page) {
    setActivePage(page);
    setSidebarOpen(false);
  }

  function cycleTheme() {
    const currentIndex = THEMES.findIndex(
      (item) => item.id === theme
    );
    const nextIndex = (currentIndex + 1) % THEMES.length;
    setTheme(THEMES[nextIndex].id);
  }

  const currentThemeLabel =
    THEMES.find((item) => item.id === theme)?.label || "Light";

  const navItems = [
    { label: "Workplace", icon: BrainCircuit },
    { label: "AI Assistant", icon: MessageSquareText },
    { label: "Knowledge Base", icon: Files },
    { label: "Evaluation", icon: ChartNoAxesCombined },
    { label: "Observability", icon: Activity },
    { label: "Security & Activity", icon: ShieldCheck },
  ];

  if (authStatus === "checking") {
    return (
      <main className="login-page">
        <section className="login-card">
          <h1>Knowledge Copilot</h1>
          <p>Checking your secure session...</p>
        </section>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="login-page">
        <section className="login-card">
          <h1>Knowledge Copilot</h1>
          <p role="alert">{authError}</p>

          <button
            className="login-submit"
            type="button"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (authStatus === "signed-out") {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className={`app-shell theme-${theme}`}>
      {sidebarOpen && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
      >
        <div className="brand">
          <div className="brand-icon">
            <BrainCircuit size={25} strokeWidth={2.2} />
          </div>

          <div className="brand-copy">
            <span className="brand-name">Knowledge Copilot</span>
            <span className="brand-subtitle">ENTERPRISE AI</span>
          </div>

          <button
            className="icon-button sidebar-close"
            aria-label="Close sidebar"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-chat-button"
          onClick={startNewConversation}
        >
          <Plus size={18} />
          <span>New conversation</span>
        </button>

        <div className="nav-section">
          <span className="section-label">WORKSPACE</span>

          <nav className="main-nav">
            {navItems.map(({ label, icon: Icon }) => (
              <button
                key={label}
                className={`nav-item ${activePage === label ? "nav-item-active" : ""
                  }`}
                onClick={() => selectPage(label)}
              >
                <Icon size={19} strokeWidth={1.8} />
                <span>{label}</span>

                {label === "AI Assistant" && (
                  <span className="nav-live-dot" />
                )}
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-spacer" />

        <div className="security-card">
          <div className="security-card-icon">
            <LockKeyhole size={18} />
          </div>

          <div>
            <p className="security-title">
              Your data stays protected
            </p>
            <p className="security-description">
              Answers are limited to documents your account can access.
            </p>
          </div>
        </div>

        <div className="sidebar-bottom">
          <button
            className={`nav-item ${activePage === "Settings" ? "nav-item-active" : ""
              }`}
            onClick={() => selectPage("Settings")}
          >
            <Settings size={19} strokeWidth={1.8} />
            <span>Settings</span>
          </button>

          <div className="profile">
            <div className="avatar">
              {(currentUser?.principal_id || "U")
                .charAt(0)
                .toUpperCase()}
            </div>

            <div className="profile-copy">
              <span className="profile-name">
                {currentUser?.principal_id || "Employee"}
              </span>
              <span className="profile-role">Signed in</span>
            </div>

            <ChevronDown size={16} className="profile-chevron" />
          </div>

          <button
            className="nav-item"
            type="button"
            onClick={handleLogout}
          >
            <LockKeyhole size={19} />
            <span>Sign out</span>
          </button>

          {authError && (
            <p role="alert" className="chat-error-summary">
              {authError}
            </p>
          )}
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={21} />
            </button>

            <div className="breadcrumb">
              <span className="breadcrumb-muted">Workspace</span>
              <span className="breadcrumb-divider">/</span>
              <span className="breadcrumb-current">{activePage}</span>
            </div>
          </div>

          <div className="topbar-actions">
            <div className="connection-status">
              <span className="status-dot" />
              <span>Local workspace</span>
            </div>

            <div className="topbar-divider" />

            <button
              className="theme-toggle"
              onClick={cycleTheme}
              aria-label={`Current theme: ${currentThemeLabel}. Click to switch theme`}
              title="Switch theme"
            >
              {theme === "light" ? (
                <Sun size={18} />
              ) : (
                <Moon size={18} />
              )}
              <span>{currentThemeLabel}</span>
            </button>

            <button
              className="icon-button topbar-settings"
              aria-label="Settings"
              onClick={() => selectPage("Settings")}
            >
              <Settings size={19} />
            </button>
          </div>
        </header>

        {activePage === "Workplace" ? (
          <Workplace
            apiBaseUrl={API_BASE_URL}
            currentUser={currentUser}
            onNavigate={selectPage}
          />
        ) : activePage === "AI Assistant" ? (
          <section className="chat-workspace">
            {messages.length === 0 ? (
              <div className="welcome-content">
                <div className="welcome-badge">
                  <Sparkles size={14} />
                  <span>YOUR ENTERPRISE KNOWLEDGE ASSISTANT</span>
                </div>

                <div className="welcome-heading">
                  <h1>
                    Good questions lead
                    <br />
                    to <span>better decisions.</span>
                  </h1>

                  <p>
                    Ask questions about your organization's knowledge.
                    Get clear answers grounded in your authorized
                    documents.
                  </p>
                </div>

                <div className="suggestion-grid">
                  {suggestions.map(
                    ({ title, description, icon: Icon, prompt }) => (
                      <button
                        className="suggestion-card"
                        key={title}
                        disabled={loading}
                        onClick={() => submitQuestion(prompt)}
                      >
                        <div className="suggestion-icon">
                          <Icon size={20} />
                        </div>

                        <span className="suggestion-title">
                          {title}
                        </span>

                        <span className="suggestion-description">
                          {description}
                        </span>

                        <ArrowUp
                          size={17}
                          className="suggestion-arrow"
                        />
                      </button>
                    )
                  )}
                </div>

                <div className="trust-note">
                  <ShieldCheck size={16} />
                  <span>
                    Evidence-based answers, with sources you can verify.
                  </span>
                </div>
              </div>
            ) : (
              <div className="conversation">
                <div className="conversation-heading">
                  <div>
                    <span className="eyebrow">CONVERSATION</span>
                    <h2>Your questions</h2>
                  </div>

                  <button
                    className="text-button"
                    onClick={startNewConversation}
                    disabled={loading}
                  >
                    <Plus size={16} />
                    New chat
                  </button>
                </div>

                {messages.map((message) => (
                  <div className="message-group" key={message.id}>
                    <div className="user-message">
                      <div className="avatar message-avatar">U</div>

                      <div>
                        <span className="message-author">You</span>
                        <p>{message.question}</p>
                      </div>
                    </div>

                    <div className="assistant-message">
                      <div className="assistant-avatar">
                        <BrainCircuit size={19} />
                      </div>

                      <div className="assistant-message-content">
                        <span className="message-author">
                          Knowledge Copilot
                        </span>

                        {message.status === "loading" && (
                          <div
                            className="demo-answer"
                            role="status"
                            aria-live="polite"
                          >
                            <div className="demo-answer-heading">
                              <Activity size={16} />
                              <span>
                                {message.answer
                                  ? "Streaming answer..."
                                  : "Searching authorized documents..."}
                              </span>
                            </div>

                            {message.answer ? (
                              <p className="answer-text">
                                {message.answer}
                                <span className="streaming-cursor">▍</span>
                              </p>
                            ) : (
                              <p>
                                Retrieving relevant evidence and
                                generating your answer.
                              </p>
                            )}

                            {Array.isArray(message.sources) &&
                              message.sources.length > 0 &&
                              !message.answer && (
                                <div className="sources-preview-pill">
                                  Found {message.sources.length} relevant document {message.sources.length === 1 ? "section" : "sections"}
                                </div>
                              )}
                          </div>
                        )}

                        {message.status === "error" && (
                          <div
                            className="demo-answer api-error"
                            role="alert"
                          >
                            <div className="demo-answer-heading">
                              <ShieldCheck size={16} />
                              Unable to answer
                            </div>

                            <p>{message.error}</p>
                          </div>
                        )}

                        {message.status === "success" && (
                          <div className="demo-answer">
                            <div className="demo-answer-heading">
                              {message.abstained ? (
                                <ShieldCheck size={16} />
                              ) : (
                                <Sparkles size={16} />
                              )}

                              <span>
                                {message.abstained
                                  ? "Insufficient evidence"
                                  : "Evidence-based answer"}
                              </span>

                              {!message.abstained && message.confidenceScore !== null && (
                                <span
                                  className="confidence-pill"
                                  title={`Retrieval confidence score: ${Math.round(message.confidenceScore * 100)}%`}
                                >
                                  {Math.round(message.confidenceScore * 100)}% confidence
                                </span>
                              )}

                              {message.model && (
                                <span
                                  className="model-tag-pill"
                                  title={`Generated with model: ${message.model}`}
                                >
                                  {message.model.includes("1.5b") ? "⚡ 1.5B Fast" : "🎯 4B Standard"}
                                </span>
                              )}
                            </div>

                            <p className="answer-text">
                              {message.answer}
                            </p>

                            {message.sources.length > 0 && (
                              <div className="sources-section">
                                <div className="sources-heading">
                                  <Files size={15} />
                                  <span>
                                    Sources ({message.sources.length})
                                  </span>
                                </div>

                                {message.sources.map((source) => (
                                  <details
                                    className="source-item"
                                    key={`${message.id}-${source.source_id}`}
                                  >
                                    <summary>
                                      <FileText size={16} />

                                      <span className="source-filename">
                                        {source.filename}
                                      </span>

                                      <span className="source-number">
                                        Source {source.source_id}
                                      </span>
                                    </summary>

                                    <div className="source-content">
                                      <p>{source.content}</p>

                                      <div className="source-metadata">
                                        Document ID: {source.document_id}
                                        {" · "}
                                        Chunk: {source.chunk_index}
                                      </div>
                                    </div>
                                  </details>
                                ))}
                              </div>
                            )}

                            {message.abstained && (
                              <span className="demo-label">
                                The backend could not find sufficient
                                supporting evidence.
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {chatError && (
                  <div className="chat-error-summary" role="status">
                    <span>{chatError}</span>

                    <button
                      className="text-button"
                      onClick={() => {
                        const lastMessage =
                          messages[messages.length - 1];

                        if (lastMessage?.status === "error") {
                          submitQuestion(lastMessage.question);
                        }
                      }}
                      disabled={loading}
                    >
                      Retry
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="composer-area">
              {showNotice && (
                <div className="demo-notice">
                  <Activity size={15} />

                  <span>
                    {loading
                      ? "Your question is being processed by the AI service."
                      : "Connected chat · Answers are generated from documents your account can access."}
                  </span>

                  <button
                    className="icon-button notice-close"
                    aria-label="Dismiss notice"
                    onClick={() => setShowNotice(false)}
                  >
                    <X size={15} />
                  </button>
                </div>
              )}

              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  submitQuestion();
                }}
              >
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      submitQuestion();
                    }
                  }}
                  placeholder="Ask a question about your documents..."
                  rows={2}
                  maxLength={2000}
                  aria-label="Ask a question"
                  disabled={loading}
                />

                <div className="composer-footer">
                  <div className="composer-footer-left">
                    <div className="composer-hint">
                      <Paperclip size={15} />
                      <span>Answers grounded in your documents</span>
                    </div>

                    <div className="model-profile-toggle" role="group" aria-label="Model Profile">
                      <button
                        type="button"
                        className={`profile-pill-btn ${modelProfile === "standard" ? "active" : ""}`}
                        onClick={() => handleModelProfileChange("standard")}
                        title="Standard Model (qwen3:4b): Comprehensive accuracy for enterprise compliance policies"
                      >
                        <Sparkles size={12} />
                        <span>Standard (4B)</span>
                      </button>
                      <button
                        type="button"
                        className={`profile-pill-btn ${modelProfile === "fast" ? "active" : ""}`}
                        onClick={() => handleModelProfileChange("fast")}
                        title="Fast Model (1.5B): ~2× faster answers for rapid lookups"
                      >
                        <Zap size={12} />
                        <span>Fast (1.5B)</span>
                      </button>
                    </div>
                  </div>

                  <button
                    className="send-button"
                    type="submit"
                    disabled={!question.trim() || loading}
                    aria-label="Send question"
                  >
                    {loading ? (
                      <span className="send-spinner" />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </form>

              <p className="composer-disclaimer">
                AI responses should be verified against the cited source
                documents.
              </p>
            </div>
          </section>
        ) : activePage === "Knowledge Base" ? (
          <KnowledgeBase apiBaseUrl={API_BASE_URL} />
        ) : activePage === "Evaluation" ? (
          <Evaluation apiBaseUrl={API_BASE_URL} />
        ) : activePage === "Observability" ? (
          <Observability apiBaseUrl={API_BASE_URL} />
        ) : activePage === "Security & Activity" ? (
          <SecurityActivity apiBaseUrl={API_BASE_URL} />
        ) : activePage === "Settings" ? (
          <SettingsPage
            apiBaseUrl={API_BASE_URL}
            currentUser={currentUser}
            theme={theme}
            onThemeChange={setTheme}
            onSignOut={handleLogout}
          />
        ) : (
          <section className="placeholder-page">
            <div className="placeholder-icon">
              <Settings size={27} />
            </div>

            <h1>{activePage}</h1>

            <p>
              This workspace is part of the dashboard plan.
            </p>

            <button
              className="primary-button"
              onClick={() => selectPage("Workplace")}
            >
              <BrainCircuit size={17} />
              Return to Workplace
            </button>
          </section>
        )}

        <footer className="app-footer">
          <span>
            <BrainCircuit size={15} />
            Knowledge Copilot
          </span>

          <span>Enterprise knowledge, made accessible.</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
