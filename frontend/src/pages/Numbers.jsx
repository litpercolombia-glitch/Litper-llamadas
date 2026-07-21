import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Phone, CheckCircle, WarningCircle, ArrowsClockwise, SimCard, Broadcast } from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_CLS = {
  verified:       "border-green-500/30 bg-green-500/10 text-green-400",
  sip_registered: "border-green-500/30 bg-green-500/10 text-green-400",
  pending:        "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  failed:         "border-red-500/30 bg-red-500/10 text-red-400",
  imported:       "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

export default function NumbersPage() {
  const [numbers, setNumbers] = useState([]);
  const [phone, setPhone] = useState("+57");
  const [country, setCountry] = useState("CO");
  const [friendly, setFriendly] = useState("");
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [lastStart, setLastStart] = useState(null);
  const [provider, setProvider] = useState("twilio");
  const [sipCfg, setSipCfg] = useState(null);
  const [sipStatus, setSipStatus] = useState(null);
  const [registering, setRegistering] = useState(false);
  const [testCall, setTestCall] = useState({ to: "+57", loading: false });

  const load = async () => {
    const [n, cfg, st] = await Promise.all([
      api.get("/numbers"),
      api.get("/numbers/sip/config").catch(() => ({ data: null })),
      api.post("/numbers/sip/test").catch(() => ({ data: null })),
    ]);
    setNumbers(n.data || []);
    setSipCfg(cfg.data);
    setSipStatus(st.data);
  };
  useEffect(() => { load(); }, []);

  const registerSip = async () => {
    setRegistering(true);
    try {
      const r = await api.post("/numbers/sip/register", {});
      toast.success(`SIP registrado — phone_number_id: ${r.data.elevenlabs_phone_number_id || "?"}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.error || e?.response?.data?.detail || e.message);
    } finally { setRegistering(false); }
  };

  const placeTestCall = async () => {
    setTestCall(t => ({ ...t, loading: true }));
    try {
      const r = await api.post("/numbers/call/test", { queue_id: "test", to_number: testCall.to });
      toast.success(`Llamada iniciada (voz ${r.data.voice}) → ${r.data.to}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail?.error || e?.response?.data?.detail || e.message);
    } finally { setTestCall(t => ({ ...t, loading: false })); }
  };

  const start = async () => {
    if (!phone.startsWith("+")) return toast.error("Usa formato E.164: +573001234567");
    setStarting(true);
    try {
      const r = await api.post("/numbers/verify/start",
        { phone_number: phone, country, friendly_name: friendly || undefined });
      setLastStart(r.data);
      if (r.data.ok) toast.success("Twilio está llamando al número. Comparte el código con el usuario.");
      else toast.error(r.data.error || "Twilio no configurado");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setStarting(false); }
  };

  const confirm = async (p) => {
    setConfirming(true);
    try {
      const r = await api.post("/numbers/verify/confirm", { phone_number: p });
      if (r.data.ok) toast.success("¡Número verificado en Twilio!");
      else toast.warning("Aún no está verificado. Reintenta en unos segundos.");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setConfirming(false); }
  };

  return (
    <Layout title="Números Conectados" subtitle="Caller ID verificado con Twilio para llamadas salientes"
      actions={
        <Button variant="outline" onClick={load} className="border-zinc-700 bg-transparent rounded-sm">
          <ArrowsClockwise size={14} />
        </Button>
      }
    >
      <div className="metal-surface p-6 mb-6" data-testid="sip-panel">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500 mb-1">
              Flujo · DIDWW SIP → ElevenLabs
            </div>
            <h3 className="text-lg text-white font-semibold flex items-center gap-2">
              <SimCard size={20} weight="duotone" /> Conectar por SIP Trunk
            </h3>
            <p className="text-xs text-zinc-500 font-mono mt-1">
              1. Conectar DIDWW SIP · 2. Registrar en ElevenLabs · 3. Probar llamada
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="w-44 bg-zinc-900 border-zinc-800 rounded-sm text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800">
                <SelectItem value="twilio">Twilio Verified ID</SelectItem>
                <SelectItem value="didww_sip">DIDWW SIP Trunk</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {provider === "didww_sip" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-3">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1">
                Estado de configuración (backend/.env)
              </div>
              {sipCfg && (
                <table className="w-full text-xs font-mono">
                  <tbody>
                    {[
                      ["SIP_PROVIDER", sipCfg.provider],
                      ["DIDWW_SIP_DOMAIN", sipCfg.sip_domain || "—"],
                      ["DIDWW_SIP_USERNAME", sipCfg.sip_username_set ? "•••••• (set)" : "—"],
                      ["DIDWW_SIP_PASSWORD", sipCfg.sip_password_set ? "•••••• (set)" : "—"],
                      ["DIDWW_OUTBOUND_TRUNK_ID", sipCfg.outbound_trunk_id || "—"],
                      ["CALLER_ID_NUMBER", sipCfg.caller_id_number || "—"],
                      ["ELEVENLABS_AGENT_ID", sipCfg.elevenlabs_agent_id || "—"],
                    ].map(([k, v]) => (
                      <tr key={k} className="border-b border-zinc-800/60">
                        <td className="py-1.5 text-zinc-500 pr-4">{k}</td>
                        <td className="py-1.5 text-zinc-200">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {sipStatus && sipStatus.issues && sipStatus.issues.length > 0 && (
                <div className="text-xs text-amber-400 mt-2">
                  {sipStatus.issues.length} campo(s) pendientes: {sipStatus.issues.join(" · ")}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 font-mono">
                Añade los valores en backend/.env y reinicia el backend, luego
                pulsa "Registrar en ElevenLabs".
              </p>
            </div>

            <div className="space-y-3">
              <Button onClick={registerSip} disabled={registering || (sipStatus && !sipStatus.ok)}
                data-testid="sip-register"
                className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">
                <Broadcast size={14} className="mr-1" />
                {registering ? "Registrando…" : "Registrar en ElevenLabs"}
              </Button>
              <div className="border-t border-zinc-800 pt-3">
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">
                  Llamada de prueba
                </label>
                <Input value={testCall.to}
                  onChange={(e) => setTestCall(t => ({ ...t, to: e.target.value }))}
                  data-testid="sip-test-to"
                  className="bg-zinc-900 border-zinc-800 rounded-sm font-mono mb-2" />
                <Button onClick={placeTestCall} disabled={testCall.loading}
                  data-testid="sip-test-call"
                  variant="outline"
                  className="w-full border-zinc-700 rounded-sm bg-transparent">
                  {testCall.loading ? "Llamando…" : "Llamada de prueba"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {provider === "twilio" && (
          <p className="text-xs text-zinc-400">
            Usa el formulario Twilio abajo para verificar un caller ID (útil sólo para pruebas o
            despliegues con Twilio como proveedor de voz).
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2 border border-zinc-800 bg-zinc-900/50 p-6">
          <h3 className="text-xs uppercase tracking-[0.15em] font-mono text-zinc-500 mb-4">Conectar nuevo número</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Teléfono (E.164)</label>
                <Input data-testid="numbers-phone" className="bg-zinc-900 border-zinc-800 rounded-sm font-mono"
                  value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+573001234567" />
              </div>
              <div>
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">País</label>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger data-testid="numbers-country" className="bg-zinc-900 border-zinc-800 rounded-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-zinc-800">
                    <SelectItem value="CO">Colombia</SelectItem>
                    <SelectItem value="EC">Ecuador</SelectItem>
                    <SelectItem value="CL">Chile</SelectItem>
                    <SelectItem value="OTHER">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Nombre (opcional)</label>
              <Input className="bg-zinc-900 border-zinc-800 rounded-sm"
                value={friendly} onChange={(e) => setFriendly(e.target.value)} placeholder="Sofía · Litper Bogotá" />
            </div>
            <Button onClick={start} disabled={starting} data-testid="numbers-start"
              className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">
              <Phone size={14} className="mr-1" /> {starting ? "Enviando código…" : "Enviar código de verificación"}
            </Button>
          </div>

          {lastStart && (
            <div className="mt-5 border border-zinc-800 bg-zinc-950 p-4 rounded-sm">
              <div className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 mb-1">
                {lastStart.ok ? "Código de validación" : "Error"}
              </div>
              {lastStart.ok ? (
                <>
                  <div className="text-4xl font-mono text-white tracking-widest mb-2" data-testid="numbers-code">
                    {lastStart.validation_code}
                  </div>
                  <p className="text-sm text-zinc-400 mb-3">
                    Twilio está llamando al número. Cuando conteste, dile que ingrese este código de 6 dígitos.
                    Luego haz clic en "Confirmar" abajo.
                  </p>
                  <Button size="sm" onClick={() => confirm(lastStart.phone_number)} disabled={confirming}
                    data-testid="numbers-confirm"
                    className="bg-white text-black hover:bg-zinc-200 rounded-sm">
                    {confirming ? "Verificando…" : "Confirmar verificación"}
                  </Button>
                </>
              ) : (
                <p className="text-sm text-red-400">{lastStart.error || `HTTP ${lastStart.status_code}`}</p>
              )}
            </div>
          )}
        </div>

        <div className="border border-zinc-800 bg-zinc-900/50 p-6">
          <h3 className="text-xs uppercase tracking-[0.15em] font-mono text-zinc-500 mb-4">¿Cómo funciona?</h3>
          <ol className="space-y-3 text-sm text-zinc-300 list-decimal list-inside">
            <li>Ingresa el número en formato E.164.</li>
            <li>Twilio llamará a ese número desde su verificador y mostrará un código.</li>
            <li>Comparte el código con la persona que contesta.</li>
            <li>Cuando lo ingrese, el número queda verificado como <span className="font-mono">Caller ID</span> de salida.</li>
            <li>Todas las llamadas IA usarán este número como remitente.</li>
          </ol>
          <p className="text-[11px] text-zinc-500 mt-4 font-mono">
            Configura TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en backend/.env.
          </p>
        </div>
      </div>

      <div className="border border-zinc-800 bg-zinc-900/40">
        <div className="px-4 py-3 border-b border-zinc-800 text-[10px] uppercase tracking-widest font-mono text-zinc-500">
          Números conectados · {numbers.length}
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500">
              <th className="text-left py-3 px-4">Teléfono</th>
              <th className="text-left py-3 px-4">Estado</th>
              <th className="text-left py-3 px-4">País</th>
              <th className="text-left py-3 px-4">Nombre</th>
              <th className="text-left py-3 px-4">Código</th>
              <th className="text-left py-3 px-4">Actualizado</th>
              <th className="py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {numbers.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-zinc-500 text-sm">Sin números conectados.</td></tr>
            )}
            {numbers.map(n => (
              <tr key={n.id} className="data-row" data-testid={`number-row-${n.id}`}>
                <td className="py-2.5 px-4 font-mono text-zinc-200">{n.phone_number}</td>
                <td className="py-2.5 px-4">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] uppercase tracking-widest font-mono border ${STATUS_CLS[n.status] || "border-zinc-700 text-zinc-400"}`}>
                    {n.status === "verified"
                      ? <CheckCircle size={11} />
                      : n.status === "failed"
                        ? <WarningCircle size={11} />
                        : <ArrowsClockwise size={11} />} {n.status}
                  </span>
                </td>
                <td className="py-2.5 px-4 text-zinc-300 font-mono text-xs">{n.country}</td>
                <td className="py-2.5 px-4 text-zinc-300">{n.friendly_name || "—"}</td>
                <td className="py-2.5 px-4 font-mono text-zinc-300">{n.validation_code || "—"}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-500">{formatDateTime(n.updated_at)}</td>
                <td className="py-2.5 px-4 text-right">
                  {n.status === "pending" && (
                    <Button size="sm" variant="ghost" onClick={() => confirm(n.phone_number)}
                      className="text-zinc-300 hover:bg-zinc-800 rounded-sm h-7 text-xs"
                      data-testid={`number-confirm-${n.id}`}>
                      Confirmar
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
