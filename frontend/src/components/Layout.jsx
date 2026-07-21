import Sidebar from "./Sidebar";
import MatrixRain from "./MatrixRain";
import Constellation from "./Constellation";
import ThemeToggle from "./ThemeToggle";
import { Toaster } from "sonner";

export default function Layout({ children, title, subtitle, actions }) {
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
        <main className="flex-1 p-8">{children}</main>
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}
