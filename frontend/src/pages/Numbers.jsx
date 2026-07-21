import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Phone, CheckCircle, WarningCircle, ArrowsClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_CLS = {
  verified: "border-green-500/30 bg-green-500/10 text-green-400",
  pending:  "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  failed:   "border-red-500/30 bg-red-500/10 text-red-400",
  imported: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

export default function NumbersPage() {
  const [numbers, setNumbers] = useState([]);
  const [phone, setPhone] = useState("+57");
  const [country, setCountry] = useState("CO");
  const [friendly, setFriendly] = useState("");
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [lastStart, setLastStart] = useState(null);

  const load = async () => {
    const r = await api.get("/numbers");
    setNumbers(r.data || []);
  };
  useEffect(() => { load(); }, []);

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
