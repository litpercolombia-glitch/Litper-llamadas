import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import Semaforo from "../components/Semaforo";

export default function CarriersPage() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    (async () => {
      const r = await api.get("/carriers");
      setRows(r.data || []);
    })();
  }, []);

  return (
    <Layout title="Transportadoras" subtitle="12 carriers colombianas con reglas de reclamo en oficina">
      <div className="border border-zinc-800 bg-zinc-900/40 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500">
              <th className="text-left py-3 px-4">Transportadora</th>
              <th className="text-right py-3 px-4">Cobertura</th>
              <th className="text-right py-3 px-4">Recaudo Máx</th>
              <th className="text-left py-3 px-4">Oficina</th>
              <th className="text-right py-3 px-4">Días Reclamo</th>
              <th className="text-right py-3 px-4">Intentos</th>
              <th className="text-left py-3 px-4">Nequi/Daviplata</th>
              <th className="text-left py-3 px-4">Notas</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.slug} className="data-row" data-testid={`carrier-row-${r.slug}`}>
                <td className="py-2.5 px-4 text-zinc-200 font-medium">{r.name}</td>
                <td className="py-2.5 px-4 font-mono text-right text-zinc-300">{r.coverage_points.toLocaleString()}</td>
                <td className="py-2.5 px-4 font-mono text-right text-zinc-300">
                  ${r.max_recaudo_cop.toLocaleString()}
                </td>
                <td className="py-2.5 px-4">
                  {r.office_claim_allowed
                    ? <span className="text-green-400 text-xs font-mono uppercase">Sí</span>
                    : <span className="text-zinc-500 text-xs font-mono uppercase">No</span>}
                </td>
                <td className="py-2.5 px-4 text-right">
                  <Semaforo value={r.office_claim_max_days == null ? "gris"
                    : r.office_claim_max_days <= 2 ? "rojo"
                    : r.office_claim_max_days <= 4 ? "amarillo" : "verde"} showLabel={false} />
                  <span className="ml-2 font-mono text-zinc-300">{r.office_claim_max_days ?? "—"}</span>
                </td>
                <td className="py-2.5 px-4 font-mono text-right text-zinc-300">{r.max_delivery_attempts}</td>
                <td className="py-2.5 px-4">
                  {r.accepts_nequi_daviplata
                    ? <span className="text-green-400 text-xs font-mono uppercase">Sí</span>
                    : <span className="text-zinc-500 text-xs font-mono uppercase">No</span>}
                </td>
                <td className="py-2.5 px-4 text-zinc-400 text-xs max-w-sm">{r.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
