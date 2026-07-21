import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { PlugsConnected, Plugs, WarningCircle, CheckCircle } from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_STYLES = {
  connected:    { cls: "text-green-400 border-green-500/30 bg-green-500/5",   Icon: CheckCircle, label: "Conectado" },
  error:        { cls: "text-red-400 border-red-500/30 bg-red-500/5",         Icon: WarningCircle, label: "Error" },
  unconfigured: { cls: "text-zinc-400 border-zinc-700 bg-zinc-900/50",        Icon: Plugs, label: "Sin configurar" },
  disconnected: { cls: "text-zinc-400 border-zinc-700 bg-zinc-900/50",        Icon: Plugs, label: "Desconectado" },
};

export default function ConnectorsPage() {
  const [conns, setConns] = useState([]);
  const [testing, setTesting] = useState({});

  const load = async () => {
    const r = await api.get("/connectors");
    setConns(r.data || []);
  };
  useEffect(() => { load(); }, []);

  const test = async (key) => {
    setTesting(t => ({ ...t, [key]: true }));
    try {
      const r = await api.post(`/connectors/${key}/test`);
      if (r.data.ok) toast.success(`${key}: conectado`);
      else toast.error(`${key}: ${r.data.error || `HTTP ${r.data.status_code || r.data.status}`}`);
      load();
    } catch (e) { toast.error(e.message); }
    finally { setTesting(t => ({ ...t, [key]: false })); }
  };

  return (
    <Layout title="Conectores" subtitle="Estado de integraciones externas">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {conns.map((c) => {
          const st = STATUS_STYLES[c.status] || STATUS_STYLES.unconfigured;
          const testable = c.key === "chatea_pro" || c.key === "supabase";
          return (
            <div key={c.key} className={`border rounded-sm p-5 ${st.cls}`}
                 data-testid={`connector-${c.key}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <PlugsConnected size={20} weight="duotone" />
                  <h3 className="text-lg font-semibold text-white">{c.name}</h3>
                </div>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 border rounded-sm text-[10px] uppercase font-mono tracking-widest">
                  <st.Icon size={12} /> {st.label}
                </span>
              </div>
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2">Clave</div>
              <div className="text-sm font-mono text-zinc-300 mb-4">{c.key}</div>
              {c.metadata?.base_url && (
                <>
                  <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1">Base URL</div>
                  <div className="text-xs font-mono text-zinc-300 break-all mb-3">{c.metadata.base_url}</div>
                </>
              )}
              {c.metadata?.url && (
                <>
                  <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1">URL</div>
                  <div className="text-xs font-mono text-zinc-300 break-all mb-3">{c.metadata.url}</div>
                </>
              )}
              {c.last_checked_at && (
                <div className="text-xs font-mono text-zinc-500 mb-3">
                  Última verificación: {formatDateTime(c.last_checked_at)}
                </div>
              )}
              {c.error_message && (
                <div className="text-xs text-red-400 mb-3 break-words">Error: {c.error_message}</div>
              )}
              {testable && (
                <Button onClick={() => test(c.key)} disabled={!!testing[c.key]}
                  data-testid={`connector-test-${c.key}`}
                  variant="outline"
                  className="border-zinc-700 bg-transparent hover:bg-zinc-800 rounded-sm">
                  {testing[c.key] ? "Probando…" : "Probar conexión"}
                </Button>
              )}
              {!testable && (
                <div className="text-xs text-zinc-500 font-mono">
                  Configuración pendiente en backend .env
                </div>
              )}
            </div>
          );
        })}
        {conns.length === 0 && <div className="text-zinc-500 text-sm">Sin conectores configurados.</div>}
      </div>
    </Layout>
  );
}
