import { useEffect, useState } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { ToastContainer } from "./components/common/Toast";
import { api } from "./services/api";
import { Overview } from "./pages/Overview";
import { SeaIceForecastPage } from "./pages/SeaIceForecast";
import { IcebergTrackingPage } from "./pages/IcebergTracking";
import { NavigationPlannerPage } from "./pages/NavigationPlanner";
import { AlertMessagePage } from "./pages/AlertMessage";
import { AssistantPage } from "./pages/Assistant";

function Page() {
  const { page } = useApp();
  switch (page) {
    case "overview":
      return <Overview />;
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
  const { setDemoMode, demoMode } = useApp();
  const [demoKnown, setDemoKnown] = useState(false);

  useEffect(() => {
    api
      .datasetsStatus()
      .then((s) => {
        setDemoMode(s.demo_mode);
        setDemoKnown(true);
      })
      .catch(() => setDemoKnown(true));
  }, [setDemoMode]);

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-navy-900 flex">
      {demoKnown && <Sidebar />}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        <Header />
        <main className="flex-1 p-4 lg:p-6 overflow-y-auto">
          <Page />
        </main>
        <footer className="px-6 py-3 text-[11px] text-navy-400 border-t border-slate-200 bg-white">
          Antarctic Navigation Decision Support System — Problem Statement 26059. Data sources and model status are
          always shown in-page.
          {demoMode
            ? " Demo routes and forecasts are synthetic and are not safe for real navigation."
            : " Predictions are estimates based on processed observations and should not be the sole basis for navigation safety decisions."}
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