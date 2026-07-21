import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/index.css";
import { useTheme } from "@/components/ThemeToggle";

import FunnelPage     from "@/pages/Funnel";
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
import ProductsPage   from "@/pages/Products";
import VipLeadsPage   from "@/pages/VipLeads";
import LoginPage      from "@/pages/Login";

// Simple operator gate — checks localStorage token exists.
function OperatorGate({ children }) {
  const location = useLocation();
  const authed = typeof window !== "undefined" && !!localStorage.getItem("litper_operator_ok");
  if (!authed) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

function App() {
  useTheme();
  useEffect(() => { document.title = "Litper Connect Hub"; }, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public funnel */}
        <Route path="/"        element={<FunnelPage />} />
        <Route path="/funnel"  element={<FunnelPage />} />
        <Route path="/login"   element={<LoginPage />} />

        {/* Internal app — operator-gated */}
        <Route path="/app"             element={<OperatorGate><CopilotPage /></OperatorGate>} />
        <Route path="/app/skills"      element={<OperatorGate><SkillsPage /></OperatorGate>} />
        <Route path="/app/metrics"     element={<OperatorGate><DashboardPage /></OperatorGate>} />
        <Route path="/app/queue"       element={<OperatorGate><QueuePage /></OperatorGate>} />
        <Route path="/app/cadence"     element={<OperatorGate><CadencePage /></OperatorGate>} />
        <Route path="/app/tasks"       element={<OperatorGate><TasksPage /></OperatorGate>} />
        <Route path="/app/messages"    element={<OperatorGate><MessagesPage /></OperatorGate>} />
        <Route path="/app/voices"      element={<OperatorGate><VoicesPage /></OperatorGate>} />
        <Route path="/app/numbers"     element={<OperatorGate><NumbersPage /></OperatorGate>} />
        <Route path="/app/carriers"    element={<OperatorGate><CarriersPage /></OperatorGate>} />
        <Route path="/app/novedades"   element={<OperatorGate><NovedadesPage /></OperatorGate>} />
        <Route path="/app/connectors"  element={<OperatorGate><ConnectorsPage /></OperatorGate>} />
        <Route path="/app/import"      element={<OperatorGate><ImportPage /></OperatorGate>} />
        <Route path="/app/products"    element={<OperatorGate><ProductsPage /></OperatorGate>} />
        <Route path="/app/vip-leads"   element={<OperatorGate><VipLeadsPage /></OperatorGate>} />

        {/* Back-compat redirects from old URLs */}
        <Route path="/copilot"    element={<Navigate to="/app" replace />} />
        <Route path="/metrics"    element={<Navigate to="/app/metrics" replace />} />
        <Route path="/queue"      element={<Navigate to="/app/queue" replace />} />
        <Route path="/cadence"    element={<Navigate to="/app/cadence" replace />} />
        <Route path="/tasks"      element={<Navigate to="/app/tasks" replace />} />
        <Route path="/messages"   element={<Navigate to="/app/messages" replace />} />
        <Route path="/voices"     element={<Navigate to="/app/voices" replace />} />
        <Route path="/numbers"    element={<Navigate to="/app/numbers" replace />} />
        <Route path="/carriers"   element={<Navigate to="/app/carriers" replace />} />
        <Route path="/novedades"  element={<Navigate to="/app/novedades" replace />} />
        <Route path="/connectors" element={<Navigate to="/app/connectors" replace />} />
        <Route path="/skills"     element={<Navigate to="/app/skills" replace />} />
        <Route path="/import"     element={<Navigate to="/app/import" replace />} />
        <Route path="/products"   element={<Navigate to="/app/products" replace />} />
        <Route path="/vip-leads"  element={<Navigate to="/app/vip-leads" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
