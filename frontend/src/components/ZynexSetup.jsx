import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { CheckCircle, Circle, PhoneCall, Robot, PlugsConnected, Key, Sparkle } from "@phosphor-icons/react";

/** Configuración en 4 pasos: el cliente solo trae su llave de ElevenLabs. */
function Paso({ n, listo, titulo, children, Icon }) {
  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5">
      <div className="flex items-center gap-3 mb-3">
        {listo ? <CheckCircle size={20} weight="fill" className="text-green-400" />
               : <Circle size={20} className="text-zinc-500" />}
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">Paso {n}</span>
        <Icon size={16} weight="duotone" className="text-zinc-300" />
        <span className="text-sm font-semibold text-white">{titulo}</span>
      </div>
      {children}
    </div>
  );
}

export default function ZynexSetup({ d, recargar }) {
  const [auto, setAuto] = useState(null);
  const [numero, setNumero] = useState("");
  const [codigo, setCodigo] = useState("");
  const [negocio, setNegocio] = useState("");
  const [hook, setHook] = useState("");
  const [busy, setBusy] = useState("");

  const cargar = () => api.get("/zcall/auto/estado").then((r) => setAuto(r.data)).catch(() => setAuto({}));
  useEffect(() => { cargar(); }, []);

  const run = async (k, fn, alListo) => {
    setBusy(k);
    try { const r = await fn(); alListo?.(r.data); await recargar(); await cargar(); return r.data; }
    catch (e) { toast.error(errorText(e)); return null; }
    finally { setBusy(""); }
  };

  const c = d.conexiones || {};
  const agentesListos = (d.agentes || []).filter((a) => a.elevenlabs_agent_id).length;
  const inp = "bg-black/40 border-zinc-700 text-white text-sm";

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400 max-w-3xl">
        Solo necesitas tu llave de ElevenLabs y tu celular. Zynex pone la telefonía, crea tus 5 agentes y conecta los resultados.
      </p>

      <Paso n={1} listo={c.elevenlabs} titulo="Conecta tu ElevenLabs" Icon={Key}>
        {c.elevenlabs
          ? <p className="text-xs text-green-300">Conectado.</p>
          : <p className="text-sm text-zinc-300">Pega tu llave en{" "}
              <Link className="underline text-cyan-300" to="/app/conexiones?tab=credenciales">Conexiones → Credenciales</Link>.
              La encuentras en elevenlabs.io → Developers → API Keys.</p>}
      </Paso>

      <Paso n={2} listo={c.numero} titulo="Verifica el número desde el que vas a llamar" Icon={PhoneCall}>
        {c.numero ? (
          <p className="text-xs text-green-300">Tus agentes llaman desde {d.config?.numero_saliente}.</p>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-zinc-300">Usa tu celular de empresa. Te llamamos, marcas un código y queda listo. No compras número.</p>
            <div className="flex flex-wrap gap-2">
              <Input aria-label="Tu celular" value={numero} onChange={(e) => setNumero(e.target.value)}
                     placeholder="314 464 4054" className={`${inp} max-w-xs`} />
              <Button disabled={!!busy || !numero.trim() || !c.elevenlabs} className="btn-cta-grad rounded-sm h-9 text-sm"
                      onClick={() => run("ver", () => api.post("/zcall/auto/numero/verificar", { numero }, { timeout: 40000 }),
                        (r) => { setCodigo(r.codigo || ""); toast.success(r.mensaje); })}>
                {busy === "ver" ? "Llamando…" : "Llamarme para verificar"}
              </Button>
            </div>
            {(codigo || auto?.numero_pendiente) && (
              <div className="border border-zinc-800 rounded-sm bg-black/30 p-4">
                {codigo && <>
                  <div className="text-xs text-zinc-400">Contesta la llamada y marca este código:</div>
                  <div className="text-3xl font-mono tracking-[0.3em] text-white my-2" data-testid="zc-codigo">{codigo}</div>
                </>}
                <Button variant="outline" disabled={!!busy} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs"
                        onClick={() => run("conf", () => api.post("/zcall/auto/numero/confirmar", {}, { timeout: 40000 }),
                          (r) => toast.success(r.mensaje))}>
                  {busy === "conf" ? "Revisando…" : "Ya marqué el código"}
                </Button>
              </div>
            )}
            {auto && auto.telefonia_zynex === false && (
              <p className="text-[11px] text-zinc-400">La telefonía de Zynex se está activando. Si ya tienes Twilio, puedes usar el tuyo en Reglas y número.</p>
            )}
          </div>
        )}
      </Paso>

      <Paso n={3} listo={agentesListos >= 5} titulo="Crea tus 5 agentes" Icon={Robot}>
        {agentesListos >= 5 ? (
          <p className="text-xs text-green-300">Listos en tu ElevenLabs. Enciéndelos en la pestaña Agentes.</p>
        ) : (
          <div className="flex flex-wrap gap-2 items-center">
            <Input aria-label="Nombre de tu negocio" value={negocio} onChange={(e) => setNegocio(e.target.value)}
                   placeholder="Nombre de tu negocio, ej. Hogar Casa Linda" className={`${inp} max-w-xs`} />
            <Button disabled={!!busy || negocio.trim().length < 2 || !c.elevenlabs} className="btn-cta-grad rounded-sm h-9 text-sm"
                    onClick={() => run("ag", () => api.post("/zcall/auto/agentes", { negocio, voice_id: "J4vZAFDEcpenkMp3f3R9" }, { timeout: 90000 }),
                      (r) => toast.success(r.mensaje))}>
              <Sparkle size={14} className="mr-1.5" /> {busy === "ag" ? "Creando…" : "Crear mis agentes"}
            </Button>
            <span className="text-[11px] text-zinc-400">Confirmación, novedad, oficina, reparto y devolución.</span>
          </div>
        )}
      </Paso>

      <Paso n={4} listo={c.webhook} titulo="Conecta los resultados" Icon={PlugsConnected}>
        {c.webhook && !hook ? (
          <p className="text-xs text-green-300">Cada llamada vuelve con su resultado a Zynex y a tu Chatea.</p>
        ) : (
          <div className="space-y-2">
            <Button disabled={!!busy || !c.elevenlabs} className="btn-cta-grad rounded-sm h-9 text-sm"
                    onClick={() => run("wh", () => api.post("/zcall/auto/webhook", {}, { timeout: 40000 }),
                      (r) => { toast.success(r.mensaje); if (!r.automatico) setHook(r.url); })}>
              {busy === "wh" ? "Conectando…" : "Conectar resultados"}
            </Button>
            {hook && <p className="text-xs text-zinc-300 break-all">Pégala en ElevenLabs → Agents → Settings → Post-call webhook: <code className="text-zinc-100">{hook}</code></p>}
          </div>
        )}
      </Paso>
    </div>
  );
}
