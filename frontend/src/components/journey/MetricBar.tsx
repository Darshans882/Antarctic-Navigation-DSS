
import type { ReactNode } from "react";

export interface JourneyMetric {
  label: string;
  value: string;
  sub?: string | null;
  tone?: "normal" | "good" | "warn" | "bad";
}

const TONE_STYLES: Record<NonNullable<JourneyMetric["tone"]>, { text: string; bg: string; icon: string }> = {
  normal: { text: "text-slate-800", bg: "bg-blue-50", icon: "text-blue-600" },
  good: { text: "text-emerald-600", bg: "bg-emerald-50", icon: "text-emerald-600" },
  warn: { text: "text-amber-600", bg: "bg-amber-50", icon: "text-amber-600" },
  bad: { text: "text-rose-600", bg: "bg-rose-50", icon: "text-rose-600" },
};

function getMetricVisuals(label: string) {
  switch (label) {
    case "Current Vessel Location":
      return {
        leftIcon: (
          <svg fill="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-10 h-10">
            <path d="M58 42l-4-4v-8c0-2-1.5-3.5-3.5-4H42V18h-4v8H16v8l-6 6v4h48v-2z" />
            <path d="M6 48s4-3 10-3 8 3 14 3 8-3 14-3 8 3 14 3v4s-4 3-10 3-8-3-14-3-8 3-14 3-8-3-14-3v-4z" />
          </svg>
        ),
      };
    case "Destination":
      return {
        leftIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
            <circle cx="12" cy="12" r="3" />
            <circle cx="12" cy="12" r="8" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-10 h-10">
            <path d="M32 16L12 48h40L32 16z" />
            <path d="M22 28L6 48h20l-4-20zM42 28l16 20H38l4-20z" opacity="0.6"/>
          </svg>
        ),
      };
    case "Journey Mode":
      return {
        leftIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12a3 3 0 11-6 0 3 3 0 016 0zm12-6a3 3 0 11-6 0 3 3 0 016 0zm0 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l5-3m-5 7l5 3M15 9l4 2m-4 4l4-2" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-10 h-10">
            <path d="M58 42l-4-4v-8c0-2-1.5-3.5-3.5-4H42V18h-4v8H16v8l-6 6v4h48v-2z" />
            <path d="M6 48s4-3 10-3 8 3 14 3 8-3 14-3 8 3 14 3v4s-4 3-10 3-8-3-14-3-8 3-14 3-8-3-14-3v-4z" />
          </svg>
        ),
      };
    case "Last Update":
      return {
        leftIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
            <circle cx="12" cy="12" r="9" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 3" />
          </svg>
        ),
        rightIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8">
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l2.5 2.5" />
          </svg>
        ),
      };
    case "Next Update":
      return {
        leftIcon: (
          <svg fill="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
            <path d="M6 2v6h.01L6 8.01 10 12l-4 4 .01.01H6V22h12v-5.99h-.01L18 16l-4-4 4-3.99-.01-.01H18V2H6zm10 14.5V20H8v-3.5l4-4 4 4zm-4-5l-4-4V4h8v3.5l-4 4z" />
          </svg>
        ),
        rightIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8">
            <circle cx="12" cy="12" r="9" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 3" />
          </svg>
        ),
      };
    case "Remaining Distance":
      return {
        leftIcon: (
          <svg fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 12a2 2 0 11-4 0 2 2 0 014 0zm10-6a2 2 0 11-4 0 2 2 0 014 0zm10 12a2 2 0 11-4 0 2 2 0 014 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.5 10.5l7-3m2 3.5l7 3.5" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-10 h-10">
             <circle cx="10" cy="48" r="4" />
             <circle cx="28" cy="32" r="3" />
             <circle cx="50" cy="16" r="4" />
             <path d="M13 45l13-11m5-4l17-12" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4" fill="none" />
          </svg>
        ),
      };
    case "Fuel Estimate":
      return {
        leftIcon: (
          <svg fill="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
            <path d="M19 12h-2V7.5a1.5 1.5 0 00-3 0V12h-3V7.5a1.5 1.5 0 00-3 0V12H6a2 2 0 00-2 2v6a2 2 0 002 2h12a2 2 0 002-2v-6a2 2 0 00-1-2zM8 7.5a1 1 0 112 0v5H8v-5zm6 0a1 1 0 112 0v5h-2v-5z" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-8 h-8">
            <path d="M48 20V8a4 4 0 00-4-4H20a4 4 0 00-4 4v48a4 4 0 004 4h24a4 4 0 004-4V32h8v16h4V20h-12zM24 12h16v12H24V12z" />
          </svg>
        ),
      };
    case "Risk Level":
      return {
        leftIcon: (
          <svg fill="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" />
          </svg>
        ),
        rightIcon: (
          <svg fill="currentColor" viewBox="0 0 64 64" className="w-8 h-8">
            <path d="M48 24h8v32h-8zM32 36h8v20h-8zM16 12h8v44h-8z" />
          </svg>
        ),
      };
    default:
      return {
        leftIcon: null,
        rightIcon: null,
      };
  }
}

export function MetricBar({ metrics }: { metrics: JourneyMetric[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m) => {
        const visuals = getMetricVisuals(m.label);
        const style = TONE_STYLES[m.tone ?? "normal"];
        
        return (
          <div
            key={m.label}
            className="bg-white rounded-[1.25rem] border border-slate-100 shadow-sm px-5 py-4 flex items-center gap-4 relative overflow-hidden group"
          >
            {/* Left Icon */}
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-colors ${style.bg} ${style.icon}`}>
              {visuals.leftIcon}
            </div>

            {/* Text Content */}
            <div className="flex-1 min-w-0 z-10 pr-10">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5 truncate">
                {m.label}
              </p>
              <p className={`text-[17px] font-bold leading-tight truncate ${style.text}`}>
                {m.value}
              </p>
              {m.sub && (
                <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                  {m.sub}
                </p>
              )}
            </div>

            {/* Right Watermark Icon */}
            <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none transition-transform group-hover:scale-110 text-blue-100">
              {visuals.rightIcon}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function MetricLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
      {children}
    </span>
  );
}