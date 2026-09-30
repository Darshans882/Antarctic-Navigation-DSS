import { useEffect, useState } from "react";
import { useApp } from "../../context/AppContext";
import { api } from "../../services/api";
import { Bars3Icon, BellAlertIcon, ChevronRightIcon, SignalIcon, WifiIcon } from "@heroicons/react/24/outline";

export function Header() {
  const { toggleSidebar, alerts, unreadAlertCount, markAlertRead, page, setPage } = useApp();
  const [backendStatus, setBackendStatus] = useState<"ok" | "error" | "loading">("loading");

  useEffect(() => {
    api.health().then(() => setBackendStatus("ok")).catch(() => setBackendStatus("error"));
  }, []);

  const isHeroPage = ["sea-ice", "icebergs", "planner", "alerts"].includes(page);
  const headerClasses = isHeroPage
    ? "absolute top-0 left-0 right-0 bg-transparent border-b border-white/20 shadow-sm"
    : "relative bg-white border-b border-slate-200/90";

  return (
    <header className={`h-16 sm:h-[68px] flex items-center px-4 lg:px-6 shrink-0 z-30 ${headerClasses}`}>
      <button
        onClick={toggleSidebar}
        className="lg:hidden mr-3 text-navy-800 hover:text-navy-900 p-1.5 rounded-md hover:bg-white/50 transition-colors shrink-0"
        title="Open Sidebar"
      >
        <Bars3Icon className="w-5 h-5" />
      </button>

      <div
        onClick={() => setPage("home")}
        className="flex items-center gap-3 cursor-pointer select-none group"
      >
        <img
          src="/app-icon.png"
          alt="Antarctic Route Explorer Logo"
          className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl object-contain shrink-0 shadow-sm transition-transform duration-200 group-hover:scale-105"
        />
        <div className="flex flex-col justify-center">
          <h2 className="page-header-title text-base sm:text-lg lg:text-xl font-black tracking-tight leading-tight flex items-center gap-1.5">
            <span className="text-navy-900 drop-shadow-sm">Antarctic</span>
            <span className="text-blue-700 drop-shadow-sm">Route Explorer</span>
          </h2>
          <p className="text-[11px] sm:text-xs text-navy-800 font-bold tracking-tight leading-none mt-0.5 drop-shadow-sm">
            Navigating a Safer Antarctic Tomorrow
          </p>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="relative group">
          <button
            type="button"
            onClick={() => setPage("alerts")}
            className="relative p-2 text-navy-800 hover:text-blue-700 hover:bg-white/50 rounded-lg transition-colors"
            title="Open alerts"
            aria-label={`Open alerts, ${unreadAlertCount} unread`}
          >
            <BellAlertIcon className="w-5 h-5 drop-shadow-sm" />
            <span className="absolute -right-1 -top-1 min-w-4 h-4 px-1 rounded-full bg-red-600 text-white text-[9px] leading-4 text-center font-bold shadow-sm">
              {unreadAlertCount > 99 ? "99+" : unreadAlertCount}
            </span>
          </button>
          {alerts.length > 0 && (
            <div className="absolute right-0 top-10 z-20 hidden group-hover:block w-72 bg-white border border-slate-200 rounded-xl shadow-lg p-3">
              <div className="flex items-center justify-between mb-2"><p className="text-xs font-semibold text-navy-800">Alert Message</p><span className="text-[10px] text-navy-400">{unreadAlertCount} unread</span></div>
              <div className="space-y-2">{alerts.slice(0, 3).map((alert) => <button key={alert.id} type="button" onClick={() => { markAlertRead(alert.id); setPage("alerts"); }} className="w-full text-left flex items-start gap-2 p-1.5 rounded hover:bg-slate-50"><BellAlertIcon className="w-4 h-4 shrink-0 text-accent-blue mt-0.5" /><span className="min-w-0"><span className="block text-[11px] font-semibold text-navy-800 truncate">{alert.title}</span><span className="block text-[10px] text-navy-400 truncate">{alert.message}</span></span></button>)}</div>
              <button type="button" onClick={() => setPage("alerts")} className="w-full flex items-center justify-end gap-1 mt-2 pt-2 border-t border-slate-100 text-[11px] font-semibold text-accent-blue">View All Alerts <ChevronRightIcon className="w-3 h-3" /></button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {backendStatus === "loading" ? (
            <SignalIcon className="w-3.5 h-3.5 text-navy-600 animate-pulse drop-shadow-sm" />
          ) : backendStatus === "ok" ? (
            <WifiIcon className="w-3.5 h-3.5 text-green-700 drop-shadow-sm" />
          ) : (
            <WifiIcon className="w-3.5 h-3.5 text-red-600 drop-shadow-sm" />
          )}
          <span className={`text-xs font-bold drop-shadow-sm ${backendStatus === "ok" ? "text-green-700" : backendStatus === "error" ? "text-red-600" : "text-navy-700"}`}>
            {backendStatus === "ok" ? "Connected" : backendStatus === "error" ? "Offline" : "Checking"}
          </span>
        </div>

      </div>
    </header>
  );
}