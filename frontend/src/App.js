import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/index.css";
import { useTheme } from "@/components/ThemeToggle";
import { api } from "@/lib/api";

import FunnelPage      from "@/pages/Funnel";
import CopilotPage     from "@/pages/Copilot";
import PedidosPage     from "@/pages/Pedidos";
import ConexionesPage  from "@/pages/Conexiones";
import MetricasPage    from "@/pages/Metricas";
import AjustesPage     from "@/pages/Ajustes";
import OnboardingPage  from "@/pages/Onboarding";
import LoginPage       from "@/pages/Login";
import RegisterPage    from "@/pages/Register";
import AuthCallback    from "@/pages/AuthCallback";

function AuthGate({ children }) {
  const location = useLocation();
  const [state, setState] = useState({ status: "checking", user: null });

  useEffect(() => {
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

function AuthRouter() {
  if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      {/* Public */}
      <Route path="/"         element={<FunnelPage />} />
      <Route path="/funnel"   element={<FunnelPage />} />
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 5-item nav */}
      <Route path="/app"             element={<AuthGate><CopilotPage /></AuthGate>} />
      <Route path="/app/pedidos"     element={<AuthGate><PedidosPage /></AuthGate>} />
      <Route path="/app/conexiones"  element={<AuthGate><ConexionesPage /></AuthGate>} />
      <Route path="/app/metricas"    element={<AuthGate><MetricasPage /></AuthGate>} />
      <Route path="/app/ajustes"     element={<AuthGate><AjustesPage /></AuthGate>} />
      <Route path="/app/onboarding"  element={<AuthGate><OnboardingPage /></AuthGate>} />

      {/* Back-compat: old routes → new tabbed hubs */}
      <Route path="/app/queue"       element={<Navigate to="/app/pedidos?tab=cola" replace />} />
      <Route path="/app/import"      element={<Navigate to="/app/pedidos?tab=importar" replace />} />
      <Route path="/app/novedades"   element={<Navigate to="/app/pedidos?tab=novedades" replace />} />
      <Route path="/app/tasks"       element={<Navigate to="/app/pedidos?tab=tickets" replace />} />
      <Route path="/app/connectors"  element={<Navigate to="/app/conexiones?tab=conectores" replace />} />
      <Route path="/app/config"      element={<Navigate to="/app/conexiones?tab=credenciales" replace />} />
      <Route path="/app/voices"      element={<Navigate to="/app/conexiones?tab=voces" replace />} />
      <Route path="/app/numbers"     element={<Navigate to="/app/conexiones?tab=numeros" replace />} />
      <Route path="/app/metrics"     element={<Navigate to="/app/metricas" replace />} />
      <Route path="/app/messages"    element={<Navigate to="/app/pedidos?tab=tickets" replace />} />
      <Route path="/app/products"    element={<Navigate to="/app/ajustes?tab=productos" replace />} />
      <Route path="/app/prompts"     element={<Navigate to="/app/ajustes?tab=prompts" replace />} />
      <Route path="/app/cadence"     element={<Navigate to="/app/ajustes?tab=cadencia" replace />} />
      <Route path="/app/carriers"    element={<Navigate to="/app/ajustes?tab=transportadoras" replace />} />
      <Route path="/app/skills"      element={<Navigate to="/app/ajustes?tab=habilidades" replace />} />
      <Route path="/app/vip-leads"   element={<Navigate to="/app/ajustes?tab=vip" replace />} />

      {/* Legacy top-level shortcuts */}
      <Route path="/copilot"    element={<Navigate to="/app" replace />} />
      <Route path="/metrics"    element={<Navigate to="/app/metricas" replace />} />
      <Route path="/queue"      element={<Navigate to="/app/pedidos?tab=cola" replace />} />
      <Route path="/connectors" element={<Navigate to="/app/conexiones?tab=conectores" replace />} />

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
