import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/index.css";
import { useTheme } from "@/components/ThemeToggle";

import DashboardPage  from "@/pages/Dashboard";
import CopilotPage    from "@/pages/Copilot";
import SkillsPage     from "@/pages/Skills";
import QueuePage      from "@/pages/Queue";
import CadencePage    from "@/pages/Cadence";
import TasksPage      from "@/pages/Tasks";
import MessagesPage   from "@/pages/Messages";
import ConnectorsPage from "@/pages/Connectors";
import CarriersPage   from "@/pages/Carriers";
import VoicesPage     from "@/pages/Voices";
import NumbersPage    from "@/pages/Numbers";
import NovedadesPage  from "@/pages/Novedades";
import ImportPage     from "@/pages/Import";

function App() {
  useTheme();  // initialises html.matrix-night / matrix-day from localStorage
  useEffect(() => { document.title = "Litper Connect Hub"; }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"           element={<CopilotPage />} />
        <Route path="/skills"     element={<SkillsPage />} />
        <Route path="/metrics"    element={<DashboardPage />} />
        <Route path="/queue"      element={<QueuePage />} />
        <Route path="/cadence"    element={<CadencePage />} />
        <Route path="/tasks"      element={<TasksPage />} />
        <Route path="/messages"   element={<MessagesPage />} />
        <Route path="/voices"     element={<VoicesPage />} />
        <Route path="/numbers"    element={<NumbersPage />} />
        <Route path="/carriers"   element={<CarriersPage />} />
        <Route path="/novedades"  element={<NovedadesPage />} />
        <Route path="/import"     element={<ImportPage />} />
        <Route path="/connectors" element={<ConnectorsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
