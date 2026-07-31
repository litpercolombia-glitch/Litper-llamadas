import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import HowItWorks from "../components/HowItWorks";
import { api } from "../lib/api";
import { PhoneCall, Play, ChatText } from "@phosphor-icons/react";
import { toast } from "sonner";

function fmtDur(v) {
  if (v == null) return "—";
  const s = typeof v === "number" ? Math.round(v > 999 ? v / 1000 : v) : parseInt(v);
  if (Number.isNaN(s)) return String(v);
  const m = Math.floor(s / 60); const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

export default function LlamadasPage() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openTx, setOpenTx] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/calls", { params: { limit: 100 } });
      setCalls(r.data?.calls || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudieron cargar las llamadas.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  return (
    <Layout title="Llamadas" subtitle="Historial post-llamada (transcript + audio) — Retell.">
      <HowItWorks
        testIdPrefix="llamadas-howitworks"
        intro="Cuando termina cada llamada, Retell nos envía el resumen: grabación, transcript, duración y resultado. Aquí las revisas."
        steps={[
          "Configura RETELL_API_KEY y provisiona un número Telnyx en tu portal.",
          "Publica un agente 'en vivo' desde Ajustes → Agentes.",
          "Cada llamada aparece aquí automáticamente vía webhook.",
        ]}
      />

      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}

      {!loading && calls.length === 0 && (
        <div className="border border-dashed border-zinc-800 rounded-sm p-10 text-center bg-zinc-900/30"
             data-testid="llamadas-empty">
          <PhoneCall size={38} className="mx-auto mb-3 text-zinc-600" weight="duotone" />
          <div className="text-lg font-semibold text-white mb-1">Aún no hay llamadas</div>
          <p className="text-sm text-zinc-400 max-w-md mx-auto">
            Publica un agente y realiza tu primera llamada de prueba.
          </p>
        </div>
      )}

      {!loading && calls.length > 0 && (
        <div className="border border-zinc-800 rounded-sm overflow-hidden" data-testid="llamadas-table">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-[10px] uppercase tracking-widest font-mono text-zinc-500">
              <tr>
                <th className="text-left px-3 py-2">Fecha</th>
                <th className="text-left px-3 py-2">Teléfono</th>
                <th className="text-left px-3 py-2">Duración</th>
                <th className="text-left px-3 py-2">Resultado</th>
                <th className="text-left px-3 py-2">Audio</th>
                <th className="text-left px-3 py-2">Transcript</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {calls.map((c) => (
                <tr key={c.call_id} data-testid={`llamadas-row-${c.call_id}`}>
                  <td className="px-3 py-2 text-zinc-400 text-xs font-mono">
                    {new Date(c.created_at).toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="px-3 py-2 text-zinc-200 font-mono">{c.telefono || "—"}</td>
                  <td className="px-3 py-2 text-zinc-300">{fmtDur(c.duracion)}</td>
                  <td className="px-3 py-2">
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 border border-zinc-700 bg-zinc-900 rounded-sm text-zinc-300">
                      {c.resultado || "sin_clasificar"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {c.recording_url ? (
                      <audio src={c.recording_url} controls preload="none"
                             className="h-7"
                             data-testid={`llamadas-audio-${c.call_id}`} />
                    ) : <span className="text-zinc-500 text-xs">—</span>}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => setOpenTx(openTx === c.call_id ? null : c.call_id)}
                      className="text-xs text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1"
                      data-testid={`llamadas-tx-toggle-${c.call_id}`}>
                      <ChatText size={12} /> {openTx === c.call_id ? "Ocultar" : "Ver"}
                    </button>
                    {openTx === c.call_id && (
                      <pre className="mt-2 text-[11px] font-mono bg-black/40 border border-zinc-800 rounded-sm p-2 max-h-40 overflow-auto whitespace-pre-wrap max-w-md"
                           data-testid={`llamadas-tx-${c.call_id}`}>
{c.transcript || "(sin transcript)"}
                      </pre>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
