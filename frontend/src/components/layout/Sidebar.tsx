import { useApp } from "../../context/AppContext";
import {
  CogIcon,
  FlagIcon,
  MapIcon,
  BellAlertIcon,
  ChatBubbleLeftEllipsisIcon,
  HomeIcon,
  Bars3Icon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";

const NAV_ITEMS: { id: import("../../types").PageId; label: string; icon: typeof HomeIcon }[] = [
  { id: "home", label: "Home", icon: HomeIcon },
  { id: "sea-ice", label: "Sea-Ice Forecast", icon: CogIcon },
  { id: "icebergs", label: "Iceberg Tracking", icon: FlagIcon },
  { id: "planner", label: "Navigation Dashboard", icon: MapIcon },
  { id: "alerts", label: "Alert Message", icon: BellAlertIcon },
  { id: "assistant", label: "AI Assistant", icon: ChatBubbleLeftEllipsisIcon },
];

export function Sidebar() {
  const { page, setPage, sidebarOpen, setSidebarOpen } = useApp();

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed top-0 left-0 z-40 h-full bg-white border-r border-slate-200 shadow-sidebar transition-all duration-300 overflow-hidden flex flex-col
          ${sidebarOpen ? "w-64 translate-x-0" : "-translate-x-full lg:translate-x-0 lg:w-16"}`}
      >
        <div className={`flex items-center py-4 border-b border-slate-100 ${sidebarOpen ? "px-3 gap-2" : "px-0 justify-center"}`}>
          
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="hidden lg:flex items-center justify-center w-8 h-8 rounded-md text-navy-600 hover:text-navy-900 hover:bg-slate-100 transition-colors shrink-0"
            title={sidebarOpen ? "Close Sidebar" : "Open Sidebar"}
          >
            {sidebarOpen ? <Bars3Icon className="w-6 h-6" /> : <ChevronRightIcon className="w-5 h-5 stroke-2" />}
          </button>

          <div className={`flex items-center ${sidebarOpen ? "" : "hidden"}`}>
            <img src="/logo.png" alt="Antarctic Route Explorer" className="h-14 w-[170px] object-contain object-left" />
          </div>

          <button
            onClick={() => setSidebarOpen(false)}
            className={`ml-auto text-navy-400 hover:text-navy-700 ${sidebarOpen ? "block lg:hidden" : "hidden"}`}
          >
            <Bars3Icon className="w-5 h-5" />
          </button>
        </div>

        <nav className={`px-3 py-3 space-y-0.5 flex-1 overflow-y-auto ${sidebarOpen ? "" : "flex flex-col items-center"}`}>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              title={!sidebarOpen ? label : undefined}
              onClick={() => {
                setPage(id);
                if (window.innerWidth < 1024) setSidebarOpen(false);
              }}
              className={`flex items-center gap-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${sidebarOpen ? "w-full px-3" : "w-10 justify-center px-0"}
                ${
                  page === id
                    ? "bg-accent-blue/10 text-accent-blue"
                    : "text-navy-600 hover:bg-slate-50 hover:text-navy-800"
                }`}
            >
              <Icon className="w-[18px] h-[18px] shrink-0" />
              <span className={`whitespace-nowrap transition-opacity duration-200 ${sidebarOpen ? "opacity-100" : "opacity-0 hidden"}`}>
                {label}
              </span>
            </button>
          ))}
        </nav>

        <div className={`px-3 py-3 border-t border-slate-100 ${sidebarOpen ? "" : "flex justify-center"}`}>
           <p className={`text-[11px] text-navy-400 text-center whitespace-nowrap ${sidebarOpen ? "block" : "hidden"}`}>
             Problem Statement 26059
           </p>
        </div>
      </aside>
    </>
  );
}