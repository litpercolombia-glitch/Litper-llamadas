import Sidebar from "./Sidebar";
import MatrixRain from "./MatrixRain";
import Constellation from "./Constellation";
import ThemeToggle from "./ThemeToggle";
import { Toaster } from "sonner";
import { useLocation } from "react-router-dom";
import { useInHub } from "./HubContext";
import PageHelp from "./PageHelp";
import { helpForRoute } from "../constants/help";

/**
 * Chrome común + instrucciones automáticas.
 *  - Página normal: las instrucciones salen de la ruta (constants/help.js).
 *  - Dentro de un contenedor de pestañas: el contenedor pasa la clave de la
 *    pestaña activa por HubContext y aquí se pintan sus instrucciones.
 *  - `helpKey` permite forzar una clave; `helpKey={false}` las oculta.
 */
export default function Layout({ children, title, subtitle, actions, helpKey }) {
  const inHub = useInHub();
  const location = useLocation();
  // When embedded inside a hub tab, drop the chrome (Sidebar + Header) so we
  // don't double it up. The hub owns the outer chrome.
  if (inHub) {
    const tabKey = helpKey === false ? null : (helpKey || (typeof inHub === "string" ? inHub : null));
    return (
      <div className="hub-embed">
        {tabKey && <PageHelp helpKey={tabKey} />}
        {actions && (
          <div className="flex flex-wrap items-center justify-end gap-2 mb-4">{actions}</div>
        )}
        {children}
      </div>
    );
  }
  const pageKey = helpKey === false ? null : (helpKey || helpForRoute(location.pathname));

  return (
    <div className="min-h-screen flex bg-zinc-950 text-zinc-100 relative">
      <Constellation density={55} />
      <MatrixRain />
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-20">
          <div className="px-8 py-5 flex items-center justify-between gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 mb-0.5">
                Command Center
              </div>
              <h2 className="text-xl font-semibold text-white">{title}</h2>
              {subtitle && <p className="text-sm text-zinc-400 mt-0.5">{subtitle}</p>}
            </div>
            <div className="flex items-center gap-2">
              {actions}
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="flex-1 p-8">
          {pageKey && <PageHelp helpKey={pageKey} />}
          {children}
        </main>
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}
