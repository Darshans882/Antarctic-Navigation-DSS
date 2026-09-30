import { useCallback, useEffect, useRef, useState } from "react";

import {

  PaperAirplaneIcon,

  SparklesIcon,

  XCircleIcon,

} from "@heroicons/react/24/outline";

import { useApp } from "../context/AppContext";

import { useAssistantChat } from "../hooks/useAssistantChat";

import { ActionConfirmations } from "./assistant/ActionConfirmations";

import { MessageContent } from "./assistant/MessageContent";



const SUGGESTIONS = [

  "What is this project?",

  "Explain how sea-ice forecasting works.",

  "What is the current sea-ice concentration?",

  "Which iceberg is nearest to my route?",

  "Explain the selected iceberg trajectory.",

  "Why is this route recommended?",

  "What are the three available routes?",

  "What is my vessel's current position?",

  "What alerts are currently active?",

  "Explain the complete architecture.",

  "What datasets does this project use?",

  "What AI/ML models are used?",

  "How does the system detect navigation risks?",

];



const HORIZON_OPTIONS = [24, 48, 72, 120];



export function AIAssistant() {

  const {

    assistantMessages: messages,

    setAssistantMessages: setMessages,

    seaIceHorizon: horizon,

    setSeaIceHorizon: setHorizon,

  } = useApp();

  const [input, setInput] = useState("");



  const { send, confirm, cancel, pending, busy } = useAssistantChat();



  const bottomRef = useRef<HTMLDivElement>(null);



  useEffect(() => {

    bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  }, [messages, busy]);



  const newChat = useCallback(() => {

    setMessages([]);



    setInput("");

  }, []);



  return (

    <div className="flex h-full flex-col gap-4">

      <div className="flex items-center justify-between mb-4">

        <div>

          <h1 className="page-title text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-slate-950">

            AI <span className="text-blue-600">Assistant</span>

          </h1>

          <p className="text-xs sm:text-sm text-slate-500 font-medium mt-1">

            Antarctic navigation co-pilot · grounded API intelligence · decision support

          </p>

        </div>

        <button

          onClick={newChat}

          disabled={busy}

          className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-navy-600 hover:bg-slate-50 transition-colors disabled:opacity-50"

        >

          Clear chat

        </button>

      </div>



      <div className="flex items-center justify-end gap-2">

        <span className="text-xs text-navy-400">Forecast horizon:</span>

        <div className="flex gap-1">

          {HORIZON_OPTIONS.map((h) => (

            <button

              key={h}

              onClick={() => setHorizon(h)}

              disabled={busy}

              className={`px-2.5 py-1 text-xs rounded-md border transition-colors disabled:opacity-50 ${

                horizon === h

                  ? "border-accent-blue bg-blue-50 text-accent-blue font-semibold"

                  : "border-slate-200 text-navy-500 hover:bg-slate-50"

              }`}

            >

              {h}h

            </button>

          ))}

        </div>

      </div>



      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-card flex flex-col min-h-[480px]">

        <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">

          <SparklesIcon className="w-4 h-4 text-accent-blue" />

          <span className="text-sm font-semibold text-navy-800">Navigation Assistant</span>

        </div>



        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-[360px]">

          {messages.length === 0 && (

            <div className="text-center py-8">

              <p className="text-sm text-navy-500 mb-3">

                Ask about routes, sea ice, icebergs, distances or fuel — or try one of these:

              </p>

              <div className="flex flex-wrap justify-center gap-2">

                {SUGGESTIONS.map((s) => (

                  <button

                    key={s}

                    onClick={() => send(s)}

                    disabled={busy}

                    className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-full text-navy-600 hover:bg-blue-50 hover:border-blue-200 hover:text-accent-blue transition-colors disabled:opacity-50"

                  >

                    {s}

                  </button>

                ))}

              </div>

            </div>

          )}



          {messages.map((m, i) => (

            <div

              key={i}

              className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}

            >

              <div

                className={`max-w-[85%] px-3 py-2 rounded-lg text-xs leading-relaxed ${

                  m.role === "user"

                    ? "bg-accent-blue text-white whitespace-pre-wrap"

                    : "bg-slate-50 border border-slate-200 text-navy-800"

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

                const warnings = m.warnings?.filter(

                  (warning) => warning !== "Predictions are model estimates; no route is guaranteed safe.",

                ) ?? [];

                const sources = m.sources?.filter(

                  (source) => !["route_details", "datasets_status"].includes(source.name),

                ) ?? [];

                if (warnings.length === 0 && sources.length === 0) return null;

                return (

                <div className="mt-1.5 max-w-[85%] space-y-1">

                  {warnings.map((w, wi) => (

                    <div

                      key={wi}

                      className="flex items-start gap-1.5 text-[10px] text-amber-700"

                    >

                      <XCircleIcon className="w-3 h-3 shrink-0 mt-0.5" />

                      <span>{w}</span>

                    </div>

                  ))}

                  {sources.length > 0 && (

                    <div className="flex flex-wrap gap-1">

                      {sources.map((s) => (

                        <span

                          key={s.name}

                          title={s.note ?? undefined}

                          className={`px-2 py-0.5 rounded-full text-[10px] border ${

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

          ))}



          {busy && (

            <div className="flex justify-start">

              <div className="px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-navy-400 flex items-center gap-2">

                <span className="w-3 h-3 rounded-full border-2 border-blue-200 border-t-accent-blue animate-spin" />

                Consulting the backend…

              </div>

            </div>

          )}

          <div ref={bottomRef} />

        </div>



        <div className="px-4 py-3 border-t border-slate-100 flex items-center gap-2">

          <input

            value={input}

            onChange={(e) => setInput(e.target.value)}

            onKeyDown={(e) => e.key === "Enter" && send(input)}

            placeholder="Ask about any panel, term or number…"

            className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-navy-800 focus:outline-none focus:ring-2 focus:ring-blue-200"

          />

          <button

            onClick={() => send(input)}

            disabled={busy}

            className="p-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue-dark transition-colors disabled:opacity-50"

          >

            <PaperAirplaneIcon className="w-4 h-4" />

          </button>

        </div>

      </div>

    </div>

  );

}