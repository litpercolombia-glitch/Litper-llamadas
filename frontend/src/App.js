import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/index.css";

import DashboardPage  from "@/pages/Dashboard";
import QueuePage      from "@/pages/Queue";
import CadencePage    from "@/pages/Cadence";
import TasksPage      from "@/pages/Tasks";
import MessagesPage   from "@/pages/Messages";
import ConnectorsPage from "@/pages/Connectors";
import CarriersPage   from "@/pages/Carriers";

function App() {
  useEffect(() => {
    // Force dark tactical theme
    document.documentElement.classList.add("dark");
    document.title = "Litper Connect Hub";
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"           element={<DashboardPage />} />
        <Route path="/queue"      element={<QueuePage />} />
        <Route path="/cadence"    element={<CadencePage />} />
        <Route path="/tasks"      element={<TasksPage />} />
        <Route path="/messages"   element={<MessagesPage />} />
        <Route path="/carriers"   element={<CarriersPage />} />
        <Route path="/connectors" element={<ConnectorsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
