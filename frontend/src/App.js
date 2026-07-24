import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/index.css";
import { useTheme } from "@/components/ThemeToggle";
import { api } from "@/lib/api";

import FunnelPage      from "@/pages/Funnel";
import DashboardPage   from "@/pages/Dashboard";
import CopilotPage     from "@/pages/Copilot";
import SkillsPage      from "@/pages/Skills";
import QueuePage       from "@/pages/Queue";
import CadencePage     from "@/pages/Cadence";
import TasksPage       from "@/pages/Tasks";
import MessagesPage    from "@/pages/Messages";
import ConnectorsPage  from "@/pages/Connectors";
import CarriersPage    from "@/pages/Carriers";
import VoicesPage      from "@/pages/Voices";
import NumbersPage     from "@/pages/Numbers";
import NovedadesPage   from "@/pages/Novedades";
import ImportPage      from "@/pages/Import";
import ProductsPage    from "@/pages/Products";
import VipLeadsPage    from "@/pages/VipLeads";
import PromptsPage     from "@/pages/Prompts";
import ConfigPage      from "@/pages/Config";
import OnboardingPage  from "@/pages/Onboarding";
import LoginPage       from "@/pages/Login";
import RegisterPage    from "@/pages/Register";
import AuthCallback    from "@/pages/AuthCallback";

/**
 * Server-authoritative auth gate. Hits `/api/auth/me` with the HttpOnly
 * cookie; while checking we show a splash instead of flashing the funnel
 * (which is what caused the "logged out on refresh" UX).
 */
function AuthGate({ children }) {
  const location = useLocation();
  const [state, setState] = useState({ status: "checking", user: null });

  useEffect(() => {
    // If arriving from OAuth callback, App-level <AuthRouter> handles it —
    // skip the /me probe to avoid the classic race condition.
    if (window.location.hash?.includes("session_id=")) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get("/auth/me");
        if (!cancelled) setState({ status: "authed", user: r.data?.user });
      } catch {
        if (!cancelled) setState({ status: "guest", user: null });
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (state.status === "checking") {
    return (
      <div className="min-h-screen grid place-items-center bg-black text-white">
        <div className="w-10 h-10 border-2 border-zinc-700 border-t-white rounded-full animate-spin" />
      </div>
    );
  }
  if (state.status === "guest") {
    localStorage.removeItem("litper_operator_ok");
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

/**
 * Detects `session_id` in the URL fragment BEFORE any routing/gating runs.
 * This is the Emergent-recommended pattern to avoid race conditions.
 */
function AuthRouter() {
  const location = useLocation();
  if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      {/* Public */}
      <Route path="/"        element={<FunnelPage />} />
      <Route path="/funnel"  element={<FunnelPage />} />
      <Route path="/login"   element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Auth-gated */}
      <Route path="/app"             element={<AuthGate><CopilotPage /></AuthGate>} />
      <Route path="/app/skills"      element={<AuthGate><SkillsPage /></AuthGate>} />
      <Route path="/app/metrics"     element={<AuthGate><DashboardPage /></AuthGate>} />
      <Route path="/app/queue"       element={<AuthGate><QueuePage /></AuthGate>} />
      <Route path="/app/cadence"     element={<AuthGate><CadencePage /></AuthGate>} />
      <Route path="/app/tasks"       element={<AuthGate><TasksPage /></AuthGate>} />
      <Route path="/app/messages"    element={<AuthGate><MessagesPage /></AuthGate>} />
      <Route path="/app/voices"      element={<AuthGate><VoicesPage /></AuthGate>} />
      <Route path="/app/numbers"     element={<AuthGate><NumbersPage /></AuthGate>} />
      <Route path="/app/carriers"    element={<AuthGate><CarriersPage /></AuthGate>} />
      <Route path="/app/novedades"   element={<AuthGate><NovedadesPage /></AuthGate>} />
      <Route path="/app/connectors"  element={<AuthGate><ConnectorsPage /></AuthGate>} />
      <Route path="/app/import"      element={<AuthGate><ImportPage /></AuthGate>} />
      <Route path="/app/products"    element={<AuthGate><ProductsPage /></AuthGate>} />
      <Route path="/app/vip-leads"   element={<AuthGate><VipLeadsPage /></AuthGate>} />
      <Route path="/app/prompts"     element={<AuthGate><PromptsPage /></AuthGate>} />
      <Route path="/app/config"      element={<AuthGate><ConfigPage /></AuthGate>} />
      <Route path="/app/onboarding"  element={<AuthGate><OnboardingPage /></AuthGate>} />

      {/* Back-compat redirects */}
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
  );
}

function App() {
  useTheme();
  useEffect(() => { document.title = "Zynex OS — Litper Connect Hub"; }, []);

  return (
    <BrowserRouter>
      <AuthRouter />
    </BrowserRouter>
  );
}

export default App;
