import { lazy, Suspense } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { ToastContainer } from "./components/common/Toast";
import { GlobalAIAssistant } from "./components/GlobalAIAssistant";

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
      <div className={`min-w-0 flex-1 flex flex-col min-h-screen transition-all duration-300 relative ${sidebarOpen ? "lg:ml-64" : "lg:ml-16"}`}>
        <Header />
        <main className="min-w-0 flex-1 p-4 lg:p-6 overflow-y-auto">
          <Suspense fallback={<div className="flex items-center justify-center h-full text-navy-500 text-sm">Loading...</div>}>
            <Page />
          </Suspense>
        </main>
      </div>
      <ToastContainer />
      <GlobalAIAssistant />
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