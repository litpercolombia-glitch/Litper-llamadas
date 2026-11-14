import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Copy, CheckCircle, WebhooksLogo, ArrowsClockwise } from "@phosphor-icons/react";

const LABELS = {
  retell: "Llamadas (Retell)", telnyx: "Telefonía (Telnyx)", twilio: "Telefonía (Twilio)",
  elevenlabs: "Voz (ElevenLabs)", whatsapp: "WhatsApp",
  chatea: "WhatsApp (Chatea Pro)", chatea_pro: "WhatsApp (Chatea Pro)",
  shopify: "Shopify", dropi: "Dropi",
};
const labelOf = (k) => LABELS[k] || String(k).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Acepta {proveedor: url} o {urls|webhooks: {...}}; ignora lo que no sea una dirección. */
function entriesOf(data) {
  const src = (data && typeof data === "object" && (data.urls || data.webhooks)) || data || {};
  if (typeof src !== "object" || Array.isArray(src)) return [];
  return Object.entries(src)
    .map(([k, v]) => [k, typeof v === "string" ? v : v?.url])
    .filter(([, v]) => typeof v === "string" && /^https?:\/\//i.test(v));
}

/** Notas del servidor por proveedor: { proveedor: "texto" }. */
function notasOf(data) {
  const n = data && typeof data === "object" ? data.notas : null;
  return n && typeof n === "object" && !Array.isArray(n) ? n : {};
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch { return false; }
  }
}

/**
 * "Tus direcciones de webhook": GET /org/webhook-urls → { proveedor: url }.
 * Si el servidor no lo tiene (404) o no devuelve direcciones, el bloque no se pinta.
 */
export default function WebhookUrls() {
  const [rows, setRows] = useState(null); // null = oculto
  const [notas, setNotas] = useState({});
  const [copied, setCopied] = useState("");
  const [rotating, setRotating] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get("/org/webhook-urls")
      .then((r) => { if (alive) { setRows(entriesOf(r.data)); setNotas(notasOf(r.data)); } })
      .catch(() => { if (alive) setRows(null); });
    return () => { alive = false; };
  }, []);

  const rotate = async () => {
    const ok = window.confirm(
      "¿Rotar tus direcciones de webhook?\n\nLas direcciones actuales dejarán de funcionar de inmediato. "
      + "Tendrás que pegar las nuevas en el panel de cada proveedor y volver a guardar tus agentes publicados."
    );
    if (!ok) return;
    setRotating(true);
    try {
      const r = await api.post("/org/webhook-urls/rotate");
      setRows(entriesOf(r.data));
      if (Object.keys(notasOf(r.data)).length) setNotas(notasOf(r.data));
      setCopied("");
      toast.success("Direcciones nuevas generadas. Las anteriores ya no funcionan: actualízalas en cada proveedor.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudieron rotar las direcciones.");
    } finally { setRotating(false); }
  };

  if (!rows || rows.length === 0) return null;

  const copy = async (key, url) => {
    if (await copyText(url)) {
      setCopied(key);
      toast.success("Dirección copiada.");
      setTimeout(() => setCopied((c) => (c === key ? "" : c)), 2000);
    } else {
      toast.error("No se pudo copiar. Selecciona la dirección y cópiala a mano.");
    }
  };

  return (
    <section className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5" data-testid="webhook-urls">
      <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1 flex items-center gap-2">
        <WebhooksLogo size={12} /> Tus direcciones de webhook
      </div>
      <p className="text-sm text-zinc-400 mb-3">
        Son exclusivas de tu empresa. Pega cada una en el panel del proveedor que corresponda para que
        nos avise de lo que pasa (una llamada que termina, un mensaje que llega). No las compartas.
      </p>
      <ul className="border border-zinc-800 rounded-sm divide-y divide-zinc-800">
        {rows.map(([key, url]) => (
          <li key={key} className="px-3 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-2"
              data-testid={`webhook-url-${key}`}>
            <div className="min-w-0 flex-1 basis-56">
              <div className="text-xs text-zinc-300">{labelOf(key)}</div>
              <div className="text-xs font-mono text-zinc-400 break-all select-all">{url}</div>
              {typeof notas[key] === "string" && notas[key] && (
                <div className="text-[11px] text-zinc-500 mt-1 leading-snug" data-testid={`webhook-nota-${key}`}>
                  {notas[key]}
                </div>
              )}
            </div>
            <Button size="sm" variant="outline" onClick={() => copy(key, url)}
                    aria-label={`Copiar la dirección de ${labelOf(key)}`}
                    data-testid={`webhook-copy-${key}`}
                    className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs shrink-0">
              {copied === key
                ? <><CheckCircle size={13} weight="fill" className="mr-1 text-green-400" /> Copiada</>
                : <><Copy size={13} className="mr-1" /> Copiar</>}
            </Button>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <Button size="sm" variant="outline" onClick={rotate} disabled={rotating}
                data-testid="webhook-rotate"
                className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
          <ArrowsClockwise size={13} className="mr-1" /> {rotating ? "Rotando…" : "Rotar direcciones"}
        </Button>
        <span className="text-[11px] text-zinc-500">
          Úsalo si una dirección se filtró. Las anteriores dejan de funcionar al instante.
        </span>
      </div>
    </section>
  );
}
