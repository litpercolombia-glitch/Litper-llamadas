import { useEffect, useState } from "react";
import Layout from "./Layout";
import EmptyState from "./EmptyState";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Switch } from "./ui/switch";
import {
  PlugsConnected, Plus, Trash, TestTube, ShieldWarning, CheckCircle, WarningCircle, FloppyDisk, Key, Warning,
} from "@phosphor-icons/react";

const AUTH_OPTIONS = [
  { key: "none",   label: "Ninguna" },
  { key: "bearer", label: "Token Bearer" },
  { key: "header", label: "Cabecera personalizada" },
];

const EMPTY_FORM = { nombre: "", url: "", auth_type: "none", secret: "", header_name: "" };

const listOf = (data) => (Array.isArray(data) ? data : (data?.servers || data?.items || []));

// "Pedir confirmación" encendido por defecto: solo se apaga si el servidor lo dice.
const normalizeTools = (tools) => (tools || []).map((t) => ({
  name: t.name,
  description: t.description || "",
  enabled: !!t.enabled,
  requires_confirm: t.requires_confirm !== false,
}));

function ServerCard({ server, onDeleted, onChanged }) {
  const [tools, setTools] = useState(normalizeTools(server.tools));
  const [result, setResult] = useState(null); // {ok, error}
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [changed, setChanged] = useState([]);       // herramientas que cambiaron y quedaron desactivadas
  const [editSecret, setEditSecret] = useState(false);
  const [newSecret, setNewSecret] = useState("");
  const [savingSecret, setSavingSecret] = useState(false);
  const hasAuth = !!server.auth_type && server.auth_type !== "none";

  // Cambiar el secreto sin borrar el conector: PATCH /mcp-servers/{id} {secret}.
  const saveSecret = async (e) => {
    e?.preventDefault?.();
    const s = newSecret.trim();
    if (!s) return;
    setSavingSecret(true);
    try {
      await api.patch(`/mcp-servers/${server.id}`, { secret: s });
      // El secreto no se conserva en el navegador ni se vuelve a mostrar.
      setNewSecret(""); setEditSecret(false); setResult(null);
      toast.success("Secreto actualizado. Pulsa «Probar conexión» para confirmar que funciona.");
      onChanged?.();
    } catch (err) {
      toast.error(errorText(err, "No se pudo cambiar el secreto."));
    } finally { setSavingSecret(false); }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await api.post(`/mcp-servers/${server.id}/test`, {}, { timeout: 60000 });
      const d = r.data || {};
      setResult({ ok: !!d.ok, error: d.error || "" });
      setChanged(Array.isArray(d.changed) ? d.changed.map((c) => (typeof c === "string" ? c : c?.name)).filter(Boolean) : []);
      if (d.ok) {
        setTools(normalizeTools(d.tools));
        setDirty(false);
        toast.success(`Conexión correcta · ${(d.tools || []).length} herramienta(s).`);
      } else {
        toast.error(d.error || "El servidor no respondió como se esperaba.");
      }
    } catch (e) {
      const msg = errorText(e, "No se pudo probar la conexión.");
      setResult({ ok: false, error: msg });
      toast.error(msg);
    } finally { setTesting(false); }
  };

  const toggle = (name, field) => {
    setTools((list) => list.map((t) => (t.name === name ? { ...t, [field]: !t[field] } : t)));
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/mcp-servers/${server.id}/tools`, {
        tools: tools.map(({ name, enabled, requires_confirm }) => ({ name, enabled, requires_confirm })),
      });
      setDirty(false);
      toast.success("Herramientas guardadas.");
    } catch (e) {
      toast.error(errorText(e, "No se pudieron guardar las herramientas."));
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!window.confirm(`¿Eliminar el conector «${server.nombre || server.name}»? El asistente dejará de usar sus herramientas.`)) return;
    try {
      await api.delete(`/mcp-servers/${server.id}`);
      toast.success("Conector eliminado.");
      onDeleted();
    } catch (e) {
      toast.error(errorText(e, "No se pudo eliminar."));
    }
  };

  const authLabel = AUTH_OPTIONS.find((o) => o.key === (server.auth_type || "none"))?.label || "Ninguna";

  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-4" data-testid={`mcp-server-${server.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white truncate">{server.nombre || server.name}</div>
          <div className="text-xs font-mono text-zinc-400 break-all">{server.url}</div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-1">
            Autenticación: {authLabel}
            {hasAuth && (server.has_secret === false ? " · sin secreto guardado" : " · secreto guardado (no se muestra)")}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          {hasAuth && !editSecret && (
            <Button size="sm" variant="outline" onClick={() => setEditSecret(true)}
                    data-testid={`mcp-secret-edit-${server.id}`}
                    className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
              <Key size={13} className="mr-1" /> Cambiar secreto
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={test} disabled={testing}
                  data-testid={`mcp-test-${server.id}`}
                  className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
            <TestTube size={13} className="mr-1" /> {testing ? "Probando…" : "Probar conexión"}
          </Button>
          <button onClick={remove} aria-label="Eliminar conector"
                  data-testid={`mcp-delete-${server.id}`}
                  className="h-8 w-8 grid place-items-center rounded-sm border border-zinc-800 hover:bg-red-500/10 hover:border-red-500/40 text-zinc-500 hover:text-red-300">
            <Trash size={13} />
          </button>
        </div>
      </div>

      {editSecret && (
        <form onSubmit={saveSecret} autoComplete="off"
              className="mt-3 border border-zinc-800 rounded-sm bg-black/30 p-3"
              data-testid={`mcp-secret-form-${server.id}`}>
          <label className="text-xs text-zinc-400 block mb-1" htmlFor={`mcp-secret-${server.id}`}>
            Nuevo {server.auth_type === "bearer" ? "token" : "valor de la cabecera"} (reemplaza al anterior)
          </label>
          <div className="flex flex-wrap gap-2">
            <Input id={`mcp-secret-${server.id}`} type="password" autoComplete="new-password"
                   value={newSecret} onChange={(e) => setNewSecret(e.target.value)}
                   placeholder="Pega aquí el secreto nuevo"
                   data-testid={`mcp-secret-input-${server.id}`}
                   className="bg-black/40 border-zinc-700 text-white font-mono text-xs flex-1 min-w-[12rem]" />
            <Button type="button" size="sm" variant="outline"
                    onClick={() => { setEditSecret(false); setNewSecret(""); }}
                    className="h-9 rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-xs">
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={!newSecret.trim() || savingSecret}
                    data-testid={`mcp-secret-save-${server.id}`}
                    className="btn-cta-grad rounded-sm h-9 text-xs">
              {savingSecret ? "Guardando…" : "Guardar secreto"}
            </Button>
          </div>
          <p className="text-[11px] text-zinc-500 mt-1.5">
            Se guarda cifrado y no se vuelve a mostrar. Por seguridad, al cambiarlo las herramientas
            pueden quedar desactivadas hasta que vuelvas a probar la conexión.
          </p>
        </form>
      )}

      {changed.length > 0 && (
        <div role="alert" data-testid={`mcp-changed-${server.id}`}
             className="mt-3 text-xs px-3 py-2 rounded-sm border border-yellow-500/20 bg-yellow-500/10 text-yellow-200 flex items-start gap-2">
          <Warning size={14} weight="fill" className="mt-0.5 shrink-0 text-yellow-400" />
          <span>
            <b className="text-yellow-100">
              {changed.length === 1 ? "Una herramienta cambió" : `${changed.length} herramientas cambiaron`} en el servidor
              y {changed.length === 1 ? "quedó desactivada" : "quedaron desactivadas"}:
            </b>{" "}
            <span className="font-mono">{changed.join(", ")}</span>. Revisa qué hace ahora cada una y vuelve a
            activarla solo si confías en el cambio.
          </span>
        </div>
      )}

      {result && (
        <div data-testid={`mcp-result-${server.id}`}
             className={`mt-3 text-xs px-3 py-2 rounded-sm border flex items-start gap-2 ${
               result.ok
                 ? "border-green-500/30 bg-green-500/10 text-green-300"
                 : "border-red-500/30 bg-red-500/10 text-red-300"
             }`}>
          {result.ok ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <WarningCircle size={14} className="mt-0.5 shrink-0" />}
          <span>{result.ok ? "Conexión correcta." : (result.error || "No se pudo conectar.")}</span>
        </div>
      )}

      <div className="mt-4">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2">
          Herramientas · {tools.length}
        </div>
        {tools.length === 0 ? (
          <p className="text-xs text-zinc-500">
            Pulsa «Probar conexión» para ver las herramientas que ofrece este servidor.
          </p>
        ) : (
          <>
            <div className="border border-zinc-800 rounded-sm divide-y divide-zinc-800">
              {tools.map((t) => (
                <div key={t.name} className="px-3 py-2.5 flex flex-wrap items-center gap-x-6 gap-y-2"
                     data-testid={`mcp-tool-${server.id}-${t.name}`}>
                  <div className="min-w-0 flex-1 basis-56">
                    <div className="text-sm font-mono text-zinc-200 break-all">{t.name}</div>
                    {t.description && <div className="text-xs text-zinc-400 mt-0.5">{t.description}</div>}
                  </div>
                  <label className="flex items-center gap-2 text-xs text-zinc-300">
                    <Switch checked={t.enabled} onCheckedChange={() => toggle(t.name, "enabled")}
                            data-testid={`mcp-tool-enabled-${server.id}-${t.name}`} />
                    Activa
                  </label>
                  <label className="flex items-center gap-2 text-xs text-zinc-300">
                    <Switch checked={t.requires_confirm} onCheckedChange={() => toggle(t.name, "requires_confirm")}
                            data-testid={`mcp-tool-confirm-${server.id}-${t.name}`} />
                    Pedir confirmación
                  </label>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3 mt-3">
              <p className="text-[11px] text-zinc-500">
                Con «Pedir confirmación» el asistente te muestra la acción y espera a que pulses «Aplicar».
              </p>
              <Button size="sm" onClick={save} disabled={saving || !dirty}
                      data-testid={`mcp-save-tools-${server.id}`}
                      className="btn-cta-grad rounded-sm h-8 text-xs shrink-0">
                <FloppyDisk size={13} className="mr-1" /> {saving ? "Guardando…" : "Guardar herramientas"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function McpConnectors() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/mcp-servers");
      setServers(listOf(r.data));
      setLoadError("");
    } catch (e) {
      setLoadError(errorText(e, "No se pudieron cargar los conectores."));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const urlOk = /^https:\/\/[^\s/]+/i.test(form.url.trim());
  const needsSecret = form.auth_type !== "none";
  const canCreate = form.nombre.trim() && urlOk
    && (!needsSecret || form.secret.trim())
    && (form.auth_type !== "header" || form.header_name.trim());

  const create = async (e) => {
    e?.preventDefault?.();
    if (!canCreate) return;
    setCreating(true);
    try {
      const body = { nombre: form.nombre.trim(), url: form.url.trim(), auth_type: form.auth_type };
      if (needsSecret) body.secret = form.secret;
      if (form.auth_type === "header") body.header_name = form.header_name.trim();
      await api.post("/mcp-servers", body);
      // El secreto no se conserva en el navegador ni se vuelve a mostrar.
      setForm(EMPTY_FORM);
      setShowForm(false);
      toast.success("Conector guardado. Ahora pulsa «Probar conexión».");
      load();
    } catch (err) {
      toast.error(errorText(err, "No se pudo guardar el conector."));
    } finally { setCreating(false); }
  };

  return (
    <Layout title="Conectores MCP">
      <div className="mb-5 border border-yellow-500/20 bg-yellow-500/10 rounded-sm p-3 text-xs text-yellow-200 flex gap-2 items-start"
           data-testid="mcp-trust-warning">
        <ShieldWarning size={16} weight="duotone" className="shrink-0 mt-0.5" />
        <span>
          Un conector MCP es una dirección web que le da al asistente herramientas nuevas para trabajar con otros sistemas.
          {" "}<b className="text-yellow-100">Conecta solo servidores en los que confíes:</b> lo que respondan llega al asistente
          y sus herramientas pueden actuar en tu nombre.
        </span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="text-[10px] uppercase font-mono tracking-widest text-zinc-500">
          {servers.length} conector{servers.length === 1 ? "" : "es"}
        </div>
        {!showForm && (
          <Button onClick={() => setShowForm(true)} data-testid="mcp-new-btn" className="btn-cta-grad rounded-sm">
            <Plus size={13} className="mr-1" /> Añadir conector
          </Button>
        )}
      </div>

      {showForm && (
        <form onSubmit={create} autoComplete="off"
              className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5 mb-5 space-y-3"
              data-testid="mcp-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Nombre</label>
              <Input value={form.nombre} onChange={(e) => set({ nombre: e.target.value })}
                     placeholder="Ej: Calendario de la clínica"
                     data-testid="mcp-form-nombre"
                     className="bg-black/40 border-zinc-700 text-white" />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Dirección (URL https)</label>
              <Input value={form.url} onChange={(e) => set({ url: e.target.value })}
                     placeholder="https://servidor.ejemplo.com/mcp" type="url" inputMode="url"
                     data-testid="mcp-form-url"
                     className="bg-black/40 border-zinc-700 text-white font-mono text-xs" />
              {form.url.trim() && !urlOk && (
                <p className="text-[11px] text-red-400 mt-1" data-testid="mcp-form-url-error">
                  La dirección debe empezar por https://
                </p>
              )}
            </div>
          </div>

          <div>
            <label className="text-xs text-zinc-400 block mb-1">Autenticación</label>
            <div className="flex flex-wrap gap-2">
              {AUTH_OPTIONS.map((o) => (
                <button key={o.key} type="button"
                        onClick={() => set({ auth_type: o.key, secret: "", header_name: "" })}
                        data-testid={`mcp-form-auth-${o.key}`}
                        className={`px-3 py-1.5 rounded-sm text-xs border transition ${
                          form.auth_type === o.key
                            ? "border-white bg-white/10 text-white"
                            : "border-zinc-700 bg-zinc-950 text-zinc-400 hover:text-white"
                        }`}>
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {needsSecret && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {form.auth_type === "header" && (
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">Nombre de la cabecera</label>
                  <Input value={form.header_name} onChange={(e) => set({ header_name: e.target.value })}
                         placeholder="X-API-Key"
                         data-testid="mcp-form-header-name"
                         className="bg-black/40 border-zinc-700 text-white font-mono text-xs" />
                </div>
              )}
              <div>
                <label className="text-xs text-zinc-400 block mb-1">
                  {form.auth_type === "bearer" ? "Token" : "Valor de la cabecera"} (secreto)
                </label>
                <Input type="password" autoComplete="new-password"
                       value={form.secret} onChange={(e) => set({ secret: e.target.value })}
                       placeholder="Pega aquí el secreto"
                       data-testid="mcp-form-secret"
                       className="bg-black/40 border-zinc-700 text-white font-mono text-xs" />
                <p className="text-[11px] text-zinc-500 mt-1">
                  Se guarda cifrado y no se vuelve a mostrar. Podrás cambiarlo después con «Cambiar secreto», sin borrar el conector.
                </p>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline"
                    onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
                    data-testid="mcp-form-cancel"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              Cancelar
            </Button>
            <Button type="submit" disabled={!canCreate || creating}
                    data-testid="mcp-form-save"
                    className="btn-cta-grad rounded-sm">
              {creating ? "Guardando…" : "Guardar conector"}
            </Button>
          </div>
        </form>
      )}

      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}

      {!loading && loadError && (
        <div className="border border-red-500/30 bg-red-500/10 text-red-300 text-sm rounded-sm p-3 flex items-center justify-between gap-3"
             data-testid="mcp-load-error">
          <span>{loadError}</span>
          <Button size="sm" variant="outline" onClick={load}
                  className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
            Reintentar
          </Button>
        </div>
      )}

      {!loading && !loadError && servers.length === 0 && !showForm && (
        <EmptyState
          icon={PlugsConnected}
          testId="mcp-empty"
          title="Aún no hay conectores MCP"
          description="Añade la dirección de un servidor MCP para que el asistente pueda usar sus herramientas, siempre con tu confirmación."
          action={{ label: "Añadir conector", onClick: () => setShowForm(true) }}
          prompt="Explícame qué es un conector MCP y cuál me serviría para mi negocio."
        />
      )}

      <div className="space-y-3">
        {servers.map((s) => <ServerCard key={s.id} server={s} onDeleted={load} onChanged={load} />)}
      </div>
    </Layout>
  );
}
