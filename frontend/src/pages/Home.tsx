import { useRef } from "react";
import { useApp } from "../context/AppContext";
import {
  SignalIcon,
  FlagIcon,
  MapIcon,
  BellAlertIcon,
  SparklesIcon,
  ArrowRightIcon
} from "@heroicons/react/24/outline";

export function HomePage() {
  const { setPage } = useApp();
  const simulatorRef = useRef<HTMLElement>(null);
  const modulesRef = useRef<HTMLElement>(null);

  const scrollToSection = (ref: React.RefObject<HTMLElement>) => {
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const navCards = [
    {
      title: "Sea-Ice Forecast",
      icon: SignalIcon,
      page: "sea-ice",
      description: "Monitor Antarctic sea ice",
      buttonText: "Open"
    },
    {
      title: "Iceberg Tracking",
      icon: FlagIcon,
      page: "icebergs",
      description: "Track iceberg movement",
      buttonText: "Open"
    },
    {
      title: "Navigation Dashboard",
      icon: MapIcon,
      page: "planner",
      description: "Generate safe routes",
      buttonText: "Open"
    },
    {
      title: "Alert Message",
      icon: BellAlertIcon,
      page: "alerts",
      description: "View navigation alerts",
      buttonText: "Open"
    },
    {
      title: "AI Assistant",
      icon: SparklesIcon,
      page: "assistant",
      description: "Ask navigation questions",
      buttonText: "Open"
    },
  ];

  const workflowSteps = [
    { label: "Observe", sub: "Satellite & Weather Data" },
    { label: "Analyze", sub: "Sea-Ice & Icebergs" },
    { label: "Plan", sub: "Route Optimization" },
    { label: "Navigate", sub: "Decision Support" },
    { label: "Alert", sub: "Risk Monitoring" },
  ];

  return (
    <div className="-m-4 min-h-full bg-transparent lg:-m-6 flex flex-col font-sans">
      
      {/* Integrated Hero & Simulator Section */}
      <section ref={simulatorRef} className="relative w-full h-[75vh] min-h-[500px] overflow-hidden border-b border-sky-100">
        
        {/* Full background Simulator */}
        <div className="absolute inset-0 z-0">
          <iframe 
            src="/simulator2.html" 
            title="Antarctic Navigation Simulator"
            className="w-full h-full border-none"
            allowFullScreen
          />
        </div>
        
        {/* Overlay to make text readable, fading down */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#f8fcff]/95 via-[#f8fcff]/70 to-transparent z-10 pointer-events-none h-3/5" />
        
        {/* Text Content */}
        <div className="absolute inset-x-0 top-0 pt-12 sm:pt-16 px-6 sm:px-12 lg:px-16 text-center flex flex-col items-center z-20 pointer-events-none">
          <h1 className="text-4xl font-bold tracking-tight text-navy-900 sm:text-5xl lg:text-6xl mb-4 pointer-events-auto drop-shadow-sm">
            Interactive <span className="text-sky-600">Antarctic Navigation</span>
          </h1>
          
          <p className="max-w-2xl text-lg leading-relaxed text-navy-800 font-medium mb-8 pointer-events-auto drop-shadow-sm">
            Antarctic DSS command center. Analyze sea-ice conditions, 
            predict iceberg movement, and generate safe navigation routes in real-time.
          </p>
          
          <button 
            onClick={() => scrollToSection(modulesRef)}
            className="pointer-events-auto inline-flex justify-center items-center gap-2 rounded-xl border-2 border-sky-200 bg-white/90 px-6 py-3 text-sm font-semibold text-navy-800 transition-all hover:-translate-y-0.5 hover:border-sky-300 hover:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500 shadow-lg backdrop-blur-sm"
          >
            Explore Navigation System
            <ArrowRightIcon className="h-4 w-4 stroke-2" />
          </button>
        </div>
      </section>

      {/* Workflow Diagram */}
      <section className="bg-white border-y border-slate-100 py-16">
        <div className="mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-12">
          <div className="text-center mb-12">
            <h2 className="text-xl font-bold tracking-tight text-navy-900">How the system works</h2>
          </div>
          
          <div className="flex flex-col md:flex-row justify-center items-center gap-4 md:gap-2 lg:gap-4 relative">
            {workflowSteps.map((step, idx) => (
              <div key={step.label} className="flex items-center w-full md:w-auto relative group">
                <div className="flex flex-col items-center justify-center w-full md:w-40 h-28 rounded-xl border border-slate-200 bg-[#f8fbfc] p-4 text-center transition-all hover:bg-sky-50 hover:border-sky-200 hover:-translate-y-1 hover:shadow-sm">
                  <span className="text-sm font-bold text-navy-900 mb-1">{step.label}</span>
                  <span className="text-xs text-navy-500">{step.sub}</span>
                </div>
                {idx < workflowSteps.length - 1 && (
                  <div className="hidden md:flex flex-1 justify-center px-2 lg:px-4 text-sky-300">
                    <ArrowRightIcon className="h-5 w-5" />
                  </div>
                )}
                {idx < workflowSteps.length - 1 && (
                  <div className="flex md:hidden justify-center py-2 text-sky-300">
                    <ArrowRightIcon className="h-5 w-5 rotate-90" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Navigation Modules Section */}
      <section ref={modulesRef} className="mx-auto w-full max-w-[1400px] px-4 sm:px-6 lg:px-8 py-10 sm:py-12 scroll-mt-6">
        <div className="mb-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-sky-600 mb-1.5">Explore the Antarctic navigation tools</p>
          <h2 className="text-xl font-bold tracking-tight text-navy-950 sm:text-2xl">System Modules</h2>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {navCards.map((card) => (
            <div
              key={card.title}
              className="group flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-sky-300 hover:shadow-md"
            >
              <div>
                <div className="inline-flex rounded-lg bg-sky-50 p-2.5 mb-3 text-sky-600 transition-colors group-hover:bg-sky-100 group-hover:text-sky-700">
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-bold text-navy-900 mb-1">{card.title}</h3>
                <p className="text-xs leading-snug text-navy-500">{card.description}</p>
              </div>
              
              <div className="mt-4 pt-3 border-t border-slate-100">
                <button
                  onClick={() => setPage(card.page as any)}
                  className="inline-flex w-full justify-between items-center gap-1.5 rounded bg-slate-50 px-3 py-1.5 text-[11px] font-semibold text-navy-700 transition-colors group-hover:bg-sky-600 group-hover:text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1"
                >
                  {card.buttonText}
                  <ArrowRightIcon className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
