import { lazy, Suspense } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { ToastContainer } from "./components/common/Toast";

const HomePage = lazy(() => import("./pages/Home").then(m => ({ default: m.HomePage })));
const SeaIceForecastPage = lazy(() => import("./pages/SeaIceForecast").then(m => ({ default: m.SeaIceForecastPage })));
const IcebergTrackingPage = lazy(() => import("./pages/IcebergTracking").then(m => ({ default: m.IcebergTrackingPage })));
const NavigationPlannerPage = lazy(() => import("./pages/NavigationPlanner").then(m => ({ default: m.NavigationPlannerPage })));
const AlertMessagePage = lazy(() => import("./pages/AlertMessage").then(m => ({ default: m.AlertMessagePage })));
const AssistantPage = lazy(() => import("./pages/Assistant").then(m => ({ default: m.AssistantPage })));

function Page() {
  const { page } = useApp();
  switch (page) {
    case "home":
      return <HomePage />;
    case "sea-ice":
      return <SeaIceForecastPage />;
    case "icebergs":
      return <IcebergTrackingPage />;
    case "planner":
      return <NavigationPlannerPage />;
    case "alerts":
      return <AlertMessagePage />;
    case "assistant":
      return <AssistantPage />;
  }
}

function Shell() {
  const { sidebarOpen } = useApp();
  return (
    <div className="min-h-screen bg-[#f0f8ff] text-navy-900 flex">
      <Sidebar />
      <div className={`min-w-0 flex-1 flex flex-col min-h-screen transition-all duration-300 ${sidebarOpen ? "lg:ml-64" : "lg:ml-16"}`}>
        <Header />
        <main className="min-w-0 flex-1 p-4 lg:p-6 overflow-y-auto">
          <Suspense fallback={<div className="flex items-center justify-center h-full text-navy-500 text-sm">Loading...</div>}>
            <Page />
          </Suspense>
        </main>
        <footer className="px-6 py-3 text-[11px] text-navy-400 border-t border-slate-200 bg-white">
          Antarctic Route Explorer — Problem Statement 26059. Data sources and model status are
          always shown in-page. Predictions are estimates based on processed observations and should not be the sole
          basis for navigation safety decisions.
        </footer>
      </div>
      <ToastContainer />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}