import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Copy, CheckCircle, Sparkle, ArrowsClockwise, WarningCircle } from "@phosphor-icons/react";

const PASOS = [
  "Pulsa «Generar mi conector» y copia la URL (solo se muestra una vez).",
  "En Claude ve a Configuración → Conectores → Agregar conector personalizado.",
  "Ponle de nombre «Zynex OS», pega la URL y guarda.",
  "Conecta también el conector de Dropi en tu Claude: Claude será el puente entre Dropi y Zynex.",
  "Escríbele a Claude: «Trae mis pedidos de Dropi y súbelos a Zynex» o «Actualiza en Dropi los resultados de las llamadas».",
];

const HERRAMIENTAS = [
  ["zynex_subir_pedidos", "Sube pedidos de Dropi a la cola de llamadas según su estado."],
  ["zynex_despachar", "Lanza ya las llamadas pendientes (respeta modo prueba y horario)."],
  ["zynex_cola", "Muestra qué está en cola o bloqueado y por qué."],
  ["zynex_resultados", "Resultados por escribir en Dropi (confirmó, corrigió dirección, etc.)."],
  ["zynex_marcar_dropi", "Marca como actualizados en Dropi los pedidos que Claude ya cambió."],
  ["zynex_estado", "Resumen: conexiones, modo, cola y métricas."],
];

export default function ConectarClaude() {
  const [conectado, setConectado] = useState(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [copiado, setCopiado] = useState(false);

  const cargar = () => api.get("/zcall/estado")
    .then((r) => setConectado(!!r.data?.conexiones?.claude))
    .catch(() => setConectado(false));
  useEffect(() => { cargar(); }, []);

  const generar = async () => {
    if (conectado && !window.confirm("Ya tienes un conector. Si generas uno nuevo, el anterior deja de funcionar y tendrás que pegar la URL nueva en Claude. ¿Continuar?")) return;
    setBusy(true);
    try {
      const r = await api.post("/zcall/claude-token");
      setUrl(r.data.url); setConectado(true); setCopiado(false);
      toast.success("Conector generado. Cópialo ahora: no se vuelve a mostrar.");
    } catch (e) {
      toast.error(errorText(e, "No se pudo generar el conector."));
    } finally { setBusy(false); }
  };

  const copiar = async () => {
    try { await navigator.clipboard.writeText(url); setCopiado(true); toast.success("URL copiada."); }
    catch { toast.error("No se pudo copiar; selecciónala y cópiala a mano."); }
  };

  return (
    <div className="space-y-5" data-testid="conectar-claude">
      <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 max-w-2xl">
            <div className="flex items-center gap-2 text-white font-semibold">
              <Sparkle size={18} weight="duotone" /> Conectar Claude
              {conectado === true && (
                <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm border border-green-500/30 bg-green-500/10 text-green-300">Conectado</span>
              )}
            </div>
            <p className="text-sm text-zinc-400 mt-1.5">
              Opera tu negocio desde tu propio Claude. Dropi no tiene API pública: Claude lee tus pedidos con su conector
              de Dropi, los sube aquí para que los agentes llamen, y después escribe en Dropi lo que dijo cada cliente.
              Cada empresa tiene su propio conector; nadie más ve tus datos.
            </p>
          </div>
          <Button onClick={generar} disabled={busy} data-testid="claude-generar"
                  className="btn-cta-grad rounded-sm h-9 text-sm shrink-0">
            <ArrowsClockwise size={14} className="mr-1.5" />
            {busy ? "Generando…" : conectado ? "Generar conector nuevo" : "Generar mi conector"}
          </Button>
        </div>

        {url && (
          <div className="mt-4 border border-zinc-800 rounded-sm bg-black/30 p-3" data-testid="claude-url">
            <div className="text-xs text-zinc-400 mb-1.5">URL de tu conector (trátala como una contraseña):</div>
            <div className="flex flex-wrap gap-2 items-center">
              <code className="text-xs font-mono text-zinc-200 break-all flex-1 min-w-[12rem]">{url}</code>
              <Button size="sm" variant="outline" onClick={copiar}
                      className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
                {copiado ? <CheckCircle size={13} className="mr-1" /> : <Copy size={13} className="mr-1" />}
                {copiado ? "Copiada" : "Copiar"}
              </Button>
            </div>
            <p className="text-[11px] text-yellow-200/80 mt-2 flex items-start gap-1.5">
              <WarningCircle size={13} className="mt-0.5 shrink-0" />
              Quien tenga esta URL puede subir pedidos y leer resultados de tu negocio. Si se filtra, genera una nueva.
            </p>
          </div>
        )}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5">
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">Cómo se conecta</div>
          <ol className="space-y-2.5">
            {PASOS.map((p, i) => (
              <li key={i} className="flex gap-3 text-sm text-zinc-300">
                <span className="h-5 w-5 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-[11px] font-mono text-zinc-400">{i + 1}</span>
                <span>{p}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5">
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">Lo que Claude puede hacer</div>
          <ul className="space-y-2.5">
            {HERRAMIENTAS.map(([n, d]) => (
              <li key={n} className="text-sm">
                <code className="text-xs font-mono text-zinc-200">{n}</code>
                <div className="text-zinc-400 text-xs mt-0.5">{d}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
