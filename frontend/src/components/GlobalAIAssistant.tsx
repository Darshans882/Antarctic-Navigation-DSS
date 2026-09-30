import { useCallback, useEffect, useRef, useState } from "react";
import {
  PaperAirplaneIcon,
  SparklesIcon,
  XMarkIcon,
  XCircleIcon,
  ArrowPathIcon,
  ChatBubbleLeftEllipsisIcon,
} from "@heroicons/react/24/outline";
import { useApp } from "../context/AppContext";
import { useAssistantChat } from "../hooks/useAssistantChat";
import { ActionConfirmations } from "./assistant/ActionConfirmations";
import { MessageContent } from "./assistant/MessageContent";
import type { PageId } from "../types";

const HORIZON_OPTIONS = [24, 48, 72, 120];

interface PageContextInfo {
  label: string;
  badge: string;
  suggestions: string[];
}

const PAGE_CONTEXT_MAP: Record<PageId, PageContextInfo> = {
  home: {
    label: "Home",
    badge: "Antarctic Overview",
    suggestions: [
      "Explain this system",
      "What can I do here?",
      "Open navigation",
      "What is this project?",
    ],
  },
  "sea-ice": {
    label: "Sea-Ice Forecast",
    badge: "Sea-Ice Intelligence",
    suggestions: [
      "Explain the current forecast",
      "What is the current sea-ice concentration?",
      "Show high sea-ice areas",
      "Change forecast to 72h",
    ],
  },
  icebergs: {
    label: "Iceberg Tracking",
    badge: "Iceberg Tracking",
    suggestions: [
      "Show the nearest iceberg",
      "Which iceberg is nearest to my route?",
      "Explain this iceberg's trajectory",
      "Track selected iceberg",
    ],
  },
  planner: {
    label: "Navigation Dashboard",
    badge: "Route Planning",
    suggestions: [
      "Explain the recommended route",
      "What are the three available routes?",
      "Check route hazards",
      "Recalculate from current position",
    ],
  },
  alerts: {
    label: "Alert Messages",
    badge: "Alert Intelligence",
    suggestions: [
      "Explain the latest alert",
      "What alerts are currently active?",
      "What changed?",
      "Which hazard is closest?",
    ],
  },
  assistant: {
    label: "AI Assistant",
    badge: "Full Assistant Mode",
    suggestions: [
      "Explain the complete architecture",
      "What datasets does this project use?",
      "What AI/ML models are used?",
      "How does the system detect navigation risks?",
    ],
  },
};

export function GlobalAIAssistant() {
  const {
    page,
    assistantMessages: messages,
    setAssistantMessages: setMessages,
    seaIceHorizon: horizon,
    setSeaIceHorizon: setHorizon,
  } = useApp();

  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");

  const { send, confirm, cancel, pending, busy } = useAssistantChat();

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (isOpen) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, busy, isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 150);
    }
  }, [isOpen]);

  const pageContext = PAGE_CONTEXT_MAP[page] ?? PAGE_CONTEXT_MAP.home;

  const clearChat = useCallback(() => {
    setMessages([]);
    setInput("");
  }, [setMessages]);

  return (
    <>
      {/* Floating Chat Panel */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Antarctic AI Assistant Chat"
          className="fixed bottom-[96px] right-4 sm:right-6 z-[1050] w-[calc(100vw-32px)] sm:w-[480px] h-[640px] max-h-[calc(100vh-120px)] bg-white/95 backdrop-blur-md rounded-2xl shadow-2xl border border-sky-100 flex flex-col overflow-hidden animate-slide-up"
        >
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-[#0b2e4f] to-[#0f4a7c] text-white flex items-center justify-between border-b border-white/10 shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative w-8 h-8 rounded-full bg-white/15 p-0.5 border border-sky-300/40 flex items-center justify-center shrink-0">
                <img
                  src="/assets/antarctic-assistant.png"
                  alt="Assistant Avatar"
                  className="w-full h-full object-contain"
                />
                <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 border-2 border-[#0b2e4f] rounded-full" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <h2 className="text-sm font-bold text-white tracking-wide truncate">
                    Antarctic AI Assistant
                  </h2>
                  <SparklesIcon className="w-3.5 h-3.5 text-sky-300 shrink-0" />
                </div>
                <div className="flex items-center gap-1 text-[11px] text-sky-200 truncate">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-sky-300" />
                  <span className="truncate">Context: {pageContext.badge}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={clearChat}
                disabled={busy}
                title="Clear conversation"
                className="p-1.5 rounded-lg text-sky-200 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className="w-4 h-4" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                title="Minimize assistant"
                className="p-1.5 rounded-lg text-sky-200 hover:text-white hover:bg-white/10 transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Subheader: Horizon Selector */}
          <div className="px-4 py-1.5 bg-slate-50/90 border-b border-slate-200/80 flex items-center justify-between text-[11px] shrink-0">
            <span className="text-navy-500 font-medium">Forecast Horizon:</span>
            <div className="flex gap-1">
              {HORIZON_OPTIONS.map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  disabled={busy}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors disabled:opacity-50 ${
                    horizon === h
                      ? "bg-accent-blue text-white shadow-sm"
                      : "bg-white border border-slate-200 text-navy-600 hover:bg-slate-100"
                  }`}
                >
                  {h}h
                </button>
              ))}
            </div>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0 text-xs">
            {messages.length === 0 ? (
              <div className="py-4 text-center space-y-3">
                <div className="w-16 h-16 mx-auto">
                  <img
                    src="/assets/antarctic-assistant.png"
                    alt="Antarctic AI Assistant"
                    className="w-full h-full object-contain filter drop-shadow(0 4px 6px rgba(15, 23, 42, 0.15))"
                  />
                </div>
                <div>
                  <p className="text-sm font-semibold text-navy-900">
                    Welcome to Antarctic AI!
                  </p>
                  <p className="text-[11px] text-navy-500 mt-0.5">
                    Grounded in real sea-ice, iceberg, and voyage telemetry.
                  </p>
                </div>

                <div className="pt-2 text-left">
                  <div className="flex items-center gap-1 text-[11px] font-semibold text-navy-700 mb-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-blue" />
                    Suggested for {pageContext.label}:
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {pageContext.suggestions.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        disabled={busy}
                        className="text-left px-3 py-2 text-xs bg-slate-50 hover:bg-blue-50/80 border border-slate-200 hover:border-blue-300 rounded-xl text-navy-700 hover:text-accent-blue transition-colors disabled:opacity-50 flex items-start gap-2 shadow-xs group"
                      >
                        <SparklesIcon className="w-3.5 h-3.5 text-accent-blue mt-0.5 shrink-0 opacity-70 group-hover:opacity-100" />
                        <span>{s}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex flex-col ${
                    m.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-xs leading-relaxed ${
                      m.role === "user"
                        ? "bg-accent-blue text-white rounded-br-xs shadow-sm whitespace-pre-wrap"
                        : "bg-slate-50 border border-slate-200/90 text-navy-900 rounded-bl-xs shadow-xs"
                    }`}
                  >
                    {m.role === "user" ? (
                      m.content
                    ) : m.content.startsWith("✓") ? (
                      <div className="flex items-center gap-2 py-1 text-emerald-800 font-medium">
                        <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center font-bold text-xs shrink-0">✓</span>
                        <span>{m.content.replace(/^✓\s*/, "")}</span>
                      </div>
                    ) : (
                      <MessageContent text={m.content} />
                    )}
                  </div>

                  {m.role === "assistant" && (() => {
                    const warnings =
                      m.warnings?.filter(
                        (warning) =>
                          warning !==
                          "Predictions are model estimates; no route is guaranteed safe.",
                      ) ?? [];
                    const sources =
                      m.sources?.filter(
                        (source) =>
                          !["route_details", "datasets_status"].includes(
                            source.name,
                          ),
                      ) ?? [];
                    if (warnings.length === 0 && sources.length === 0) return null;
                    return (
                      <div className="mt-1.5 max-w-[88%] space-y-1">
                        {warnings.map((w, wi) => (
                          <div
                            key={wi}
                            className="flex items-start gap-1.5 text-[10px] text-amber-700 bg-amber-50/80 border border-amber-200/70 px-2 py-1 rounded-md"
                          >
                            <XCircleIcon className="w-3 h-3 shrink-0 mt-0.5 text-amber-600" />
                            <span>{w}</span>
                          </div>
                        ))}
                        {sources.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {sources.map((s) => (
                              <span
                                key={s.name}
                                title={s.note ?? undefined}
                                className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                  s.status === "error"
                                    ? "border-red-200 bg-red-50 text-red-600"
                                    : s.demo
                                      ? "border-amber-200 bg-amber-50 text-amber-700"
                                      : "border-emerald-200 bg-emerald-50 text-emerald-700"
                                }`}
                              >
                                {s.name}
                                {s.demo ? " · demo" : " · data"}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {m.role === "assistant" && pending.length > 0 && (
                    <ActionConfirmations
                      pending={pending}
                      busy={busy}
                      onConfirm={confirm}
                      onCancel={cancel}
                    />
                  )}
                </div>
              ))
            )}

            {busy && (
              <div className="flex justify-start">
                <div className="px-3.5 py-2 rounded-2xl rounded-bl-xs bg-slate-50 border border-slate-200 text-xs text-navy-500 flex items-center gap-2 shadow-xs">
                  <span className="w-3.5 h-3.5 rounded-full border-2 border-blue-200 border-t-accent-blue animate-spin" />
                  <span>Consulting Antarctic backend…</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input Bar */}
          <div className="p-3 bg-white border-t border-slate-200/80 flex items-center gap-2 shrink-0">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              placeholder={`Ask about ${pageContext.label.toLowerCase()}...`}
              className="flex-1 text-xs border border-slate-200 rounded-xl px-3 py-2 bg-slate-50/60 text-navy-900 focus:outline-none focus:ring-2 focus:ring-sky-200 focus:bg-white transition-all placeholder:text-navy-400"
            />
            <button
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
              title="Send message"
              className="p-2 bg-accent-blue hover:bg-accent-blue-dark text-white rounded-xl transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-xs shrink-0"
            >
              <PaperAirplaneIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Welcome Speech Bubble */}
      {!isOpen && (
        <div
          role="status"
          className="fixed bottom-[126px] right-4 sm:right-6 z-[1050] max-w-[300px] w-auto bg-white border border-sky-200 rounded-2xl p-3.5 shadow-xl text-navy-900 text-sm speech-bubble-anim cursor-pointer select-none group"
          onClick={() => setIsOpen(true)}
        >
          <div className="flex items-start gap-2">
            <div className="flex items-start gap-2">
              <ChatBubbleLeftEllipsisIcon className="w-5 h-5 text-sky-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="raga-typing-line raga-typing-line-first font-bold text-[#0b2e4f]">Hi, I'm Raga</p>
                <p className="raga-typing-line raga-typing-line-second text-xs text-navy-600 leading-snug">
                  How can I assist you today?
                </p>
              </div>
            </div>
          </div>

          {/* Speech Bubble Arrow pointing towards the penguin */}
          <div className="absolute -bottom-2 right-7 w-4 h-4 bg-white border-b border-r border-sky-200 transform rotate-45" />
        </div>
      )}

      {/* Floating Penguin Assistant Character Launcher */}
      <div
        className="fixed bottom-5 right-5 sm:bottom-6 sm:right-6 z-[1050] flex flex-col items-center select-none"
      >
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          aria-label="Antarctic AI Assistant"
          title="Ask Antarctic AI"
          className="relative block w-[76px] sm:w-[88px] md:w-[100px] lg:w-[108px] cursor-pointer focus:outline-none transition-transform active:scale-95"
        >
          <img
            src="/assets/antarctic-assistant.png"
            alt="Antarctic AI Assistant"
            className="w-full h-auto object-contain pointer-events-none penguin-float-anim"
          />
        </button>
      </div>
    </>
  );
}
