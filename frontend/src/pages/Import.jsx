import { useState, useMemo } from "react";
import Layout from "../components/Layout";
import { api, formatCOP } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  FileXls, UploadSimple, CheckCircle, WarningOctagon, Info,
  CircleNotch, Package, ArrowRight,
} from "@phosphor-icons/react";

const CARRIERS = [
  ["interrapidisimo", "Interrapidísimo"],
  ["envia",           "Envía"],
  ["coordinadora",    "Coordinadora"],
  ["servientrega",    "Servientrega"],
  ["tcc",             "TCC"],
  ["domina",          "Domina"],
  ["wiilog",          "Wiilog"],
  ["jamv-drive",      "Jamv Drive"],
  ["veloces",         "Veloces"],
  ["99-minutos",      "99 Minutos"],
  ["fleetex",         "Fleetex"],
  ["de-rocha",        "De Rocha"],
];

export default function ImportPage() {
  const [file, setFile] = useState(null);
  const [sheets, setSheets] = useState([]);
  const [sheet, setSheet] = useState("");
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [selected, setSelected] = useState({}); // order_key -> true
  const [overrides, setOverrides] = useState({}); // order_key -> carrier_slug
  const [defaultCarrier, setDefaultCarrier] = useState("");
  const [country, setCountry] = useState("CO");
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const onFilePick = async (f) => {
    setFile(f);
    setPreview(null);
    setResult(null);
    setSheets([]);
    setSheet("");
    if (!f) return;
    if (f.name.toLowerCase().endsWith(".csv")) return; // CSV = single sheet
    // Ask backend for the sheet names
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await api.post("/dropi/sheets", fd);
      setSheets(r.data.sheets || []);
      setSheet(r.data.sheets?.[0] || "");
    } catch {
      // ignore, we'll fall back to default sheet
    }
  };

  const runPreview = async () => {
    if (!file) { toast.error("Selecciona un archivo primero."); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (sheet) fd.append("sheet", sheet);
      const r = await api.post("/dropi/preview", fd);
      setPreview(r.data);
      // pre-select every row that has a valid carrier
      const sel = {};
      (r.data.consolidated || []).forEach((e) => {
        if (e.carrier_slug) sel[e.order_key] = true;
      });
      setSelected(sel);
      setOverrides({});
      toast.success(
        `${r.data.consolidated_count} órdenes detectadas (de ${r.data.raw_row_count} filas).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error analizando el archivo.");
    } finally {
      setUploading(false);
    }
  };

  const stats = useMemo(() => {
    if (!preview) return null;
    const selKeys = Object.keys(selected).filter((k) => selected[k]);
    const rows = preview.consolidated.filter((e) => selKeys.includes(e.order_key));
    const recaudo = rows.reduce((s, e) => s + (e.total_amount || 0), 0);
    const combos = rows.filter((e) => e.is_combo).length;
    return { count: rows.length, recaudo, combos };
  }, [preview, selected]);

  const runImport = async () => {
    if (!preview) return;
    const orderKeys = Object.keys(selected).filter((k) => selected[k]);
    if (!orderKeys.length) { toast.error("Selecciona al menos una orden."); return; }
    setImporting(true);
    try {
      const r = await api.post("/dropi/import", {
        preview_id: preview.id,
        order_keys: orderKeys,
        carrier_overrides: overrides,
        default_carrier_slug: defaultCarrier || null,
        country,
      });
      setResult(r.data);
      toast.success(`${r.data.imported_count} importadas · ${r.data.skipped_count} omitidas · ${r.data.error_count} errores.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error importando.");
    } finally {
      setImporting(false);
    }
  };

  const toggleAll = (val) => {
    if (!preview) return;
    const next = {};
    preview.consolidated.forEach((e) => { next[e.order_key] = val; });
    setSelected(next);
  };

  return (
    <Layout
      title="Importar desde Dropi"
      subtitle="Excel · CSV — consolidación combo-safe (1 orden = 1 fila incluso si tiene combos/promos)"
    >
      {/* ---------- STEP 1: PICK FILE ---------- */}
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-6 mb-6"
        data-testid="import-step-file">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded bg-zinc-800 border border-zinc-700 grid place-items-center text-xs font-mono">1</div>
          <h3 className="text-sm font-mono uppercase tracking-widest text-zinc-300">Cargar archivo</h3>
        </div>

        <label className="block border-2 border-dashed border-zinc-700 rounded-lg p-8 text-center cursor-pointer hover:border-zinc-500 transition"
          data-testid="import-file-dropzone">
          <input
            type="file"
            className="hidden"
            accept=".xlsx,.xls,.csv"
            onChange={(e) => onFilePick(e.target.files?.[0] || null)}
            data-testid="import-file-input"
          />
          <FileXls size={40} className="mx-auto text-zinc-500 mb-2" weight="duotone" />
          <div className="text-sm text-zinc-300">
            {file ? file.name : "Arrastra o haz clic para seleccionar (.xlsx / .xls / .csv)"}
          </div>
          <div className="text-[11px] font-mono text-zinc-500 mt-1">
            Detecta automáticamente las columnas de Dropi
          </div>
        </label>

        {sheets.length > 1 && (
          <div className="mt-4 flex items-center gap-3">
            <span className="text-xs text-zinc-400 font-mono">Hoja:</span>
            <Select value={sheet} onValueChange={setSheet}>
              <SelectTrigger className="w-64" data-testid="import-sheet-select">
                <SelectValue placeholder="Elige hoja" />
              </SelectTrigger>
              <SelectContent>
                {sheets.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="mt-4 flex gap-3">
          <Button
            onClick={runPreview}
            disabled={!file || uploading}
            data-testid="import-analyze-btn"
          >
            {uploading ? <CircleNotch className="animate-spin" size={14} /> : <UploadSimple size={14} />}
            {uploading ? "Analizando…" : "Analizar archivo"}
          </Button>
        </div>
      </section>

      {/* ---------- STEP 2: PREVIEW ---------- */}
      {preview && (
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-6 mb-6"
          data-testid="import-step-preview">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded bg-zinc-800 border border-zinc-700 grid place-items-center text-xs font-mono">2</div>
            <h3 className="text-sm font-mono uppercase tracking-widest text-zinc-300">Previsualizar y confirmar</h3>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Kpi label="Filas del archivo" value={preview.raw_row_count} />
            <Kpi label="Órdenes reales" value={preview.consolidated_count}
                 hint="agrupadas por ID/Guía" testId="import-kpi-orders" />
            <Kpi label="Combos detectados" value={preview.combo_orders} />
            <Kpi label="Recaudo total" value={formatCOP(preview.total_recaudo, "COP")}
                 testId="import-kpi-recaudo" />
          </div>

          {/* Warnings */}
          {preview.warnings?.length > 0 && (
            <div className="mb-4 space-y-2">
              {preview.warnings.map((w, i) => (
                <div key={i} className="border border-amber-500/40 bg-amber-500/5 rounded px-3 py-2 text-xs text-amber-200 flex gap-2 items-start"
                  data-testid={`import-warning-${i}`}>
                  <WarningOctagon size={16} className="text-amber-400 shrink-0 mt-0.5" />
                  <div>{w}</div>
                </div>
              ))}
            </div>
          )}

          {/* Naive-vs-correct callout */}
          {preview.total_recaudo_if_summed_naively > preview.total_recaudo && (
            <div className="border border-emerald-500/30 bg-emerald-500/5 rounded px-3 py-2 text-xs text-emerald-200 mb-4 flex gap-2 items-start"
              data-testid="import-recaudo-callout">
              <Info size={16} className="text-emerald-400 shrink-0 mt-0.5" />
              <div>
                Si sumaras el recaudo fila por fila obtendrías&nbsp;
                <b>{formatCOP(preview.naive_sum_recaudo, "COP")}</b> —
                el correcto (una vez por orden) es&nbsp;
                <b>{formatCOP(preview.total_recaudo, "COP")}</b>.
              </div>
            </div>
          )}

          {/* Import defaults */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div>
              <label className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">Carrier por defecto (si no se detecta)</label>
              <Select value={defaultCarrier} onValueChange={setDefaultCarrier}>
                <SelectTrigger data-testid="import-default-carrier">
                  <SelectValue placeholder="— sin default —" />
                </SelectTrigger>
                <SelectContent>
                  {CARRIERS.map(([slug, name]) => (
                    <SelectItem key={slug} value={slug}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">País</label>
              <Select value={country} onValueChange={setCountry}>
                <SelectTrigger data-testid="import-country">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CO">Colombia</SelectItem>
                  <SelectItem value="EC">Ecuador</SelectItem>
                  <SelectItem value="CL">Chile</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Table */}
          <div className="border border-zinc-800 rounded overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900/60 border-b border-zinc-800">
              <Checkbox
                checked={preview.consolidated.every((e) => selected[e.order_key])}
                onCheckedChange={(v) => toggleAll(!!v)}
                data-testid="import-select-all"
              />
              <span className="text-xs text-zinc-400 font-mono">Seleccionar todo</span>
              <div className="ml-auto text-xs text-zinc-500 font-mono">
                {stats?.count || 0} seleccionadas · {formatCOP(stats?.recaudo || 0, "COP")}
              </div>
            </div>
            <div className="max-h-[420px] overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead className="w-32">ID / Guía</TableHead>
                    <TableHead>Cliente</TableHead>
                    <TableHead>Productos</TableHead>
                    <TableHead className="w-40">Carrier</TableHead>
                    <TableHead className="w-28 text-right">Recaudo</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.consolidated.map((e) => {
                    const sel = !!selected[e.order_key];
                    const eff = overrides[e.order_key] || e.carrier_slug || defaultCarrier || "";
                    return (
                      <TableRow key={e.order_key} data-testid={`import-row-${e.order_key}`}>
                        <TableCell>
                          <Checkbox
                            checked={sel}
                            onCheckedChange={(v) => setSelected({ ...selected, [e.order_key]: !!v })}
                            data-testid={`import-select-${e.order_key}`}
                          />
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          <div className="text-zinc-100">{e.external_ref || "-"}</div>
                          <div className="text-zinc-500">{e.tracking_number || "-"}</div>
                        </TableCell>
                        <TableCell className="text-sm">
                          <div className="text-zinc-100">{e.customer_name || "—"}</div>
                          <div className="text-xs text-zinc-500">{e.customer_phone || "—"} · {e.city || "—"}</div>
                        </TableCell>
                        <TableCell className="text-sm">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-zinc-200">{e.products_display || "—"}</span>
                            {e.is_combo && (
                              <Badge variant="outline" className="border-blue-500/40 text-blue-300 bg-blue-500/10 text-[10px]">
                                <Package size={11} className="mr-1" /> combo × {e.items_count}
                              </Badge>
                            )}
                            {!e.is_combo && e.items_count > 0 && (
                              <span className="text-[10px] text-zinc-500 font-mono">
                                {e.items_count} ítem
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={eff}
                            onValueChange={(v) => setOverrides({ ...overrides, [e.order_key]: v })}
                          >
                            <SelectTrigger className="h-8 text-xs"
                              data-testid={`import-carrier-${e.order_key}`}>
                              <SelectValue placeholder="Elegir carrier" />
                            </SelectTrigger>
                            <SelectContent>
                              {CARRIERS.map(([slug, name]) => (
                                <SelectItem key={slug} value={slug}>{name}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          {!e.carrier_slug && (
                            <div className="text-[10px] text-amber-400 mt-1">
                              {e.carrier_raw ? `no reconocido: ${e.carrier_raw}` : "sin carrier"}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatCOP(e.total_amount, "COP")}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={runImport}
              disabled={importing || !stats?.count}
              data-testid="import-commit-btn"
            >
              {importing ? <CircleNotch className="animate-spin" size={14} /> : <ArrowRight size={14} />}
              Importar {stats?.count || 0} órdenes
            </Button>
          </div>
        </section>
      )}

      {/* ---------- STEP 3: RESULT ---------- */}
      {result && (
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-6"
          data-testid="import-step-result">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle size={20} className="text-green-400" weight="duotone" />
            <h3 className="text-sm font-mono uppercase tracking-widest text-zinc-300">Resultado</h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Kpi label="Importadas" value={result.imported_count} testId="import-result-imported" />
            <Kpi label="Omitidas (ya existen)" value={result.skipped_count} testId="import-result-skipped" />
            <Kpi label="Errores" value={result.error_count} testId="import-result-errors" />
          </div>
          {result.errors?.length > 0 && (
            <div className="mt-3 space-y-1 text-xs">
              {result.errors.map((er, i) => (
                <div key={i} className="text-red-300 font-mono">· orden {er.order_key}: {er.error}</div>
              ))}
            </div>
          )}
        </section>
      )}
    </Layout>
  );
}

function Kpi({ label, value, hint, testId }) {
  return (
    <div className="border border-zinc-800 rounded p-3 bg-zinc-900/60" data-testid={testId}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{label}</div>
      <div className="text-lg font-semibold text-zinc-100 mt-0.5">{value}</div>
      {hint && <div className="text-[10px] text-zinc-500 mt-0.5">{hint}</div>}
    </div>
  );
}
