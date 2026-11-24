import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { errorText, fetchOrgProfile, setOrgProfileCache } from "../lib/assistant";
import { refreshPacks } from "../lib/packs";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Storefront, FloppyDisk, Package, CheckCircle, DownloadSimple } from "@phosphor-icons/react";

const FIELD_CLS = "bg-black/40 border-zinc-700 text-white";
const SELECT_CLS = "w-full h-9 rounded-md bg-black/40 border border-zinc-700 text-white text-sm px-3 focus:outline-none focus:border-zinc-500";

const SECTORES = [
  "Salud y clínicas", "Inmobiliaria", "Restaurantes y hotelería", "Tienda en línea",
  "Comercio y tiendas físicas", "Servicios profesionales", "Educación",
  "Finanzas y cobranza", "Logística y envíos", "Otro",
];
const PAISES = [
  ["CO", "Colombia"], ["MX", "México"], ["AR", "Argentina"], ["CL", "Chile"], ["PE", "Perú"],
  ["EC", "Ecuador"], ["ES", "España"], ["US", "Estados Unidos"], ["BR", "Brasil"], ["OTRO", "Otro"],
];
const MONEDAS = ["COP", "MXN", "ARS", "CLP", "PEN", "USD", "EUR", "BRL"];
const ZONAS = [
  "America/Bogota", "America/Mexico_City", "America/Argentina/Buenos_Aires", "America/Santiago",
  "America/Lima", "America/Guayaquil", "America/New_York", "America/Sao_Paulo", "Europe/Madrid",
];
const IDIOMAS = [["es", "Español"], ["en", "Inglés"], ["pt", "Portugués"]];

const browserTz = () => {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch { return ""; }
};

const EMPTY = {
  empresa: "", sector: "", pais: "", moneda: "", zona_horaria: "", idioma: "es",
  nombre_asistente: "", descripcion: "",
};

/** Formulario del perfil del negocio: GET/PUT /org/profile. */
export function BusinessProfileForm({ onSaved, submitLabel = "Guardar perfil", testIdPrefix = "org-profile" }) {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchOrgProfile(true).then((p) => {
      if (!alive) return;
      const clean = {};
      Object.keys(EMPTY).forEach((k) => { clean[k] = p?.[k] ?? EMPTY[k]; });
      if (!clean.zona_horaria) clean.zona_horaria = browserTz();
      setForm(clean);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const zonas = form.zona_horaria && !ZONAS.includes(form.zona_horaria) ? [form.zona_horaria, ...ZONAS] : ZONAS;
  const sectores = form.sector && !SECTORES.includes(form.sector) ? [form.sector, ...SECTORES] : SECTORES;
  const monedas = form.moneda && !MONEDAS.includes(form.moneda) ? [form.moneda, ...MONEDAS] : MONEDAS;
  const paises = form.pais && !PAISES.some(([k]) => k === form.pais) ? [[form.pais, form.pais], ...PAISES] : PAISES;

  const save = async (e) => {
    e?.preventDefault?.();
    if (!form.empresa.trim()) { toast.error("Escribe el nombre de tu empresa."); return; }
    setSaving(true);
    try {
      const body = { ...form, empresa: form.empresa.trim(), nombre_asistente: form.nombre_asistente.trim() };
      const r = await api.put("/org/profile", body);
      const saved = r.data?.profile || r.data || body;
      setOrgProfileCache({ ...body, ...saved });
      toast.success("Perfil del negocio guardado.");
      onSaved?.({ ...body, ...saved });
    } catch (err) {
      toast.error(errorText(err, "No se pudo guardar el perfil del negocio."));
    } finally { setSaving(false); }
  };

  if (loading) return <div className="text-zinc-500 font-mono text-sm">Cargando…</div>;

  return (
    <form onSubmit={save} className="space-y-3" data-testid={`${testIdPrefix}-form`}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Nombre de la empresa</label>
          <Input value={form.empresa} onChange={(e) => set({ empresa: e.target.value })}
                 placeholder="Ej: Clínica Sonrisa" data-testid={`${testIdPrefix}-empresa`} className={FIELD_CLS} />
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Sector</label>
          <select value={form.sector} onChange={(e) => set({ sector: e.target.value })}
                  data-testid={`${testIdPrefix}-sector`} className={SELECT_CLS}>
            <option value="">Elige uno…</option>
            {sectores.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">País</label>
          <select value={form.pais} onChange={(e) => set({ pais: e.target.value })}
                  data-testid={`${testIdPrefix}-pais`} className={SELECT_CLS}>
            <option value="">Elige uno…</option>
            {paises.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Moneda</label>
          <select value={form.moneda} onChange={(e) => set({ moneda: e.target.value })}
                  data-testid={`${testIdPrefix}-moneda`} className={SELECT_CLS}>
            <option value="">Elige una…</option>
            {monedas.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Zona horaria</label>
          <select value={form.zona_horaria} onChange={(e) => set({ zona_horaria: e.target.value })}
                  data-testid={`${testIdPrefix}-zona`} className={SELECT_CLS}>
            <option value="">Elige una…</option>
            {zonas.map((z) => <option key={z} value={z}>{z.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Idioma</label>
          <select value={form.idioma} onChange={(e) => set({ idioma: e.target.value })}
                  data-testid={`${testIdPrefix}-idioma`} className={SELECT_CLS}>
            {IDIOMAS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Nombre de tu asistente</label>
          <Input value={form.nombre_asistente} onChange={(e) => set({ nombre_asistente: e.target.value })}
                 placeholder="Lyan" maxLength={30}
                 data-testid={`${testIdPrefix}-asistente`} className={FIELD_CLS} />
          <p className="text-[11px] text-zinc-500 mt-1">Si lo dejas vacío se llamará Lyan.</p>
        </div>
        <div className="md:col-span-2">
          <label className="text-xs text-zinc-400 block mb-1">¿A qué se dedica tu negocio?</label>
          <Textarea rows={3} value={form.descripcion} onChange={(e) => set({ descripcion: e.target.value })}
                    placeholder="Ej: Atendemos pacientes de odontología general y ortodoncia, con cita previa, de lunes a sábado."
                    data-testid={`${testIdPrefix}-descripcion`} className={`${FIELD_CLS} text-sm`} />
        </div>
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={saving} data-testid={`${testIdPrefix}-save`} className="btn-cta-grad rounded-sm">
          <FloppyDisk size={13} className="mr-1" /> {saving ? "Guardando…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}

const packList = (data) => (Array.isArray(data) ? data : (data?.packs || data?.items || []));
const packId = (p) => p.id || p.key || p.pack || p.slug;

/** Paquetes opcionales: GET /packs · POST /packs/{pack}/install. */
export function PacksSection() {
  const [packs, setPacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [installing, setInstalling] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/packs");
      setPacks(packList(r.data));
      setError("");
    } catch (e) {
      setError(errorText(e, "No se pudieron cargar los paquetes."));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const install = async (p) => {
    const id = packId(p);
    setInstalling(id);
    try {
      await api.post(`/packs/${encodeURIComponent(id)}/install`);
      toast.success(`Paquete «${p.nombre || p.name || id}» instalado. Sus pantallas ya aparecen en el menú.`);
      load();
      refreshPacks();
    } catch (e) {
      toast.error(errorText(e, "No se pudo instalar el paquete."));
    } finally { setInstalling(null); }
  };

  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5" data-testid="packs-card">
      <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1 flex items-center gap-2">
        <Package size={12} /> Paquetes
      </div>
      <p className="text-sm text-zinc-400 mb-3">
        Funciones opcionales para un tipo de operación concreto. Instala solo las que necesites; el resto de la
        plataforma funciona igual sin ellas.
      </p>
      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}
      {!loading && error && (
        <div className="text-sm text-red-300 border border-red-500/30 bg-red-500/10 rounded-sm px-3 py-2 flex items-center justify-between gap-3"
             data-testid="packs-error">
          <span>{error}</span>
          <Button size="sm" variant="outline" onClick={load}
                  className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Reintentar</Button>
        </div>
      )}
      {!loading && !error && packs.length === 0 && (
        <p className="text-sm text-zinc-500" data-testid="packs-empty">No hay paquetes disponibles por ahora.</p>
      )}
      <div className="space-y-2">
        {packs.map((p) => {
          const id = packId(p);
          const installed = p.installed === true || p.instalado === true;
          return (
            <div key={id} className="border border-zinc-800 rounded-sm bg-zinc-950 px-3 py-3 flex flex-wrap items-center gap-3"
                 data-testid={`pack-${id}`}>
              <div className="min-w-0 flex-1 basis-56">
                <div className="text-sm font-semibold text-white">{p.nombre || p.name || id}</div>
                {(p.descripcion || p.description) && (
                  <div className="text-xs text-zinc-400 mt-0.5">{p.descripcion || p.description}</div>
                )}
              </div>
              {installed ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest px-2 py-1 border border-green-500/20 bg-green-500/10 text-green-400 rounded-sm">
                  <CheckCircle size={12} weight="fill" /> Instalado
                </span>
              ) : (
                <Button size="sm" onClick={() => install(p)} disabled={installing === id}
                        data-testid={`pack-install-${id}`}
                        className="btn-cta-grad rounded-sm h-8 text-xs">
                  <DownloadSimple size={13} className="mr-1" /> {installing === id ? "Instalando…" : "Instalar"}
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Tarjeta completa para Perfil: formulario + paquetes. */
export default function BusinessProfile() {
  return (
    <div className="space-y-6 max-w-5xl mb-6">
      <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5" data-testid="org-profile-card">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1 flex items-center gap-2">
          <Storefront size={12} /> Perfil del negocio
        </div>
        <p className="text-sm text-zinc-400 mb-4">
          El asistente usa estos datos para hablar como tu empresa: en tu idioma, con tu moneda y tu horario.
        </p>
        <BusinessProfileForm />
      </div>
      <PacksSection />
    </div>
  );
}
