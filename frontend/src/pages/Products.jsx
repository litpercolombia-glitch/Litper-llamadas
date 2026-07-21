import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatCOP } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import { toast } from "sonner";
import {
  Package, Plus, Trash, FloppyDisk, Tag, Sparkle, X,
} from "@phosphor-icons/react";

function PromotionRow({ p, onChange, onDelete }) {
  return (
    <div className="border border-zinc-800 rounded p-3 bg-zinc-950/40 space-y-2"
      data-testid={`promo-row-${p.id || p.sku_pattern}`}>
      <div className="grid grid-cols-2 gap-2">
        <Input placeholder="SKU pattern (ej. PROTECTOR MAS FUNDAS)"
          value={p.sku_pattern || ""}
          onChange={(e) => onChange({ ...p, sku_pattern: e.target.value })}
          data-testid="promo-sku" />
        <Input placeholder="Nombre comercial (que dice Sofía)"
          value={p.nombre_comercial || ""}
          onChange={(e) => onChange({ ...p, nombre_comercial: e.target.value })}
          data-testid="promo-name" />
      </div>
      <Input placeholder="Descripción" value={p.descripcion || ""}
        onChange={(e) => onChange({ ...p, descripcion: e.target.value })} />
      <div className="grid grid-cols-3 gap-2">
        <Input type="number" placeholder="Precio lista"
          value={p.precio_lista || 0}
          onChange={(e) => onChange({ ...p, precio_lista: +e.target.value || 0 })} />
        <Input type="number" placeholder="Precio promo"
          value={p.precio_promo || 0}
          onChange={(e) => onChange({ ...p, precio_promo: +e.target.value || 0 })}
          data-testid="promo-price" />
        <Input placeholder="Bonos (coma)"
          value={(p.bonos || []).join(", ")}
          onChange={(e) => onChange({ ...p, bonos: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
      </div>
      <div className="flex justify-between items-center">
        <label className="text-xs text-zinc-400 flex items-center gap-2">
          <input type="checkbox" checked={p.activa !== false}
            onChange={(e) => onChange({ ...p, activa: e.target.checked })} />
          Activa
        </label>
        <Button variant="ghost" size="sm" onClick={onDelete}
          className="text-red-400 hover:text-red-300" data-testid="promo-delete">
          <Trash size={14} /> Eliminar
        </Button>
      </div>
    </div>
  );
}

function ProductEditor({ product, onSave, onCancel }) {
  const [p, setP] = useState(product || {
    nombre: "", descripcion: "", instrucciones_llamada: "",
    promotions: [], activo: true,
  });

  const addPromo = () => setP({
    ...p,
    promotions: [...(p.promotions || []), {
      id: crypto.randomUUID(), sku_pattern: "", nombre_comercial: "",
      descripcion: "", precio_lista: 0, precio_promo: 0, bonos: [], activa: true,
    }],
  });

  const updatePromo = (idx, np) => {
    const promotions = [...(p.promotions || [])];
    promotions[idx] = np;
    setP({ ...p, promotions });
  };

  const deletePromo = (idx) => {
    const promotions = [...(p.promotions || [])];
    promotions.splice(idx, 1);
    setP({ ...p, promotions });
  };

  return (
    <div className="border border-zinc-800 rounded-lg p-5 bg-zinc-900/40 backdrop-blur-md space-y-3"
      data-testid="product-editor">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-mono uppercase tracking-widest text-zinc-300">
          {p.id ? "Editar producto" : "Nuevo producto"}
        </h3>
        <Button variant="ghost" size="sm" onClick={onCancel}><X size={14} /></Button>
      </div>
      <Input placeholder="Nombre técnico" value={p.nombre}
        onChange={(e) => setP({ ...p, nombre: e.target.value })}
        data-testid="product-nombre" />
      <Textarea placeholder="Descripción del producto" value={p.descripcion || ""}
        onChange={(e) => setP({ ...p, descripcion: e.target.value })} rows={2} />
      <div>
        <label className="text-[11px] font-mono uppercase tracking-widest text-zinc-500">
          Instrucciones para la llamada (variables: {"{product_name} {promo_name} {promo_price} {customer_name} {tracking}"})
        </label>
        <Textarea rows={3}
          value={p.instrucciones_llamada || ""}
          onChange={(e) => setP({ ...p, instrucciones_llamada: e.target.value })}
          placeholder="Tono cálido, colombiano..."
          data-testid="product-instrucciones" />
      </div>

      <div className="pt-3 border-t border-zinc-800">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-400">
            <Tag size={12} className="inline mr-1" /> Promociones ({(p.promotions || []).length})
          </h4>
          <Button size="sm" variant="outline" onClick={addPromo} data-testid="promo-add">
            <Plus size={12} /> Añadir promo
          </Button>
        </div>
        <div className="space-y-2">
          {(p.promotions || []).map((pr, i) => (
            <PromotionRow key={pr.id || i} p={pr}
              onChange={(np) => updatePromo(i, np)}
              onDelete={() => deletePromo(i)} />
          ))}
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-3">
        <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
        <Button onClick={() => onSave(p)} data-testid="product-save">
          <FloppyDisk size={14} /> Guardar
        </Button>
      </div>
    </div>
  );
}

export default function ProductsPage() {
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/products");
      setItems(r.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async (p) => {
    try {
      if (p.id) {
        await api.patch(`/products/${p.id}`, p);
        toast.success("Producto actualizado.");
      } else {
        await api.post("/products", p);
        toast.success("Producto creado.");
      }
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error guardando.");
    }
  };

  const del = async (id) => {
    if (!window.confirm("¿Eliminar producto?")) return;
    await api.delete(`/products/${id}`);
    load();
  };

  return (
    <Layout
      title="Productos & Promociones"
      subtitle="Cataloga tus productos y define las promos que se mencionan en las llamadas."
      actions={<Button onClick={() => setEditing({})} data-testid="product-new-btn">
        <Plus size={14} /> Nuevo producto
      </Button>}
    >
      {editing !== null && (
        <div className="mb-6">
          <ProductEditor product={editing.id ? editing : null}
            onSave={save} onCancel={() => setEditing(null)} />
        </div>
      )}

      {loading && <div className="text-zinc-400 text-sm">Cargando…</div>}

      {!loading && items.length === 0 && (
        <div className="border border-dashed border-zinc-700 rounded-lg p-10 text-center text-zinc-400">
          Aún no hay productos. Crea el primero.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {items.map((p) => (
          <div key={p.id} className="border border-zinc-800 rounded-lg p-5 bg-zinc-900/40 backdrop-blur-md"
            data-testid={`product-card-${p.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Package size={16} className="text-zinc-300" weight="duotone" />
                  <h3 className="text-white font-semibold">{p.nombre}</h3>
                  {!p.activo && <Badge variant="outline" className="border-zinc-600 text-zinc-400">inactivo</Badge>}
                </div>
                {p.descripcion && <p className="text-xs text-zinc-400 mt-1">{p.descripcion}</p>}
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="outline" onClick={() => setEditing(p)}
                  data-testid={`product-edit-${p.id}`}>Editar</Button>
                <Button size="sm" variant="ghost" onClick={() => del(p.id)}
                  className="text-red-400 hover:text-red-300"><Trash size={14} /></Button>
              </div>
            </div>
            {(p.promotions?.length > 0) && (
              <div className="mt-3">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>SKU pattern</TableHead>
                      <TableHead>Nombre comercial</TableHead>
                      <TableHead className="text-right">Precio promo</TableHead>
                      <TableHead>Bonos</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {p.promotions.map((pr) => (
                      <TableRow key={pr.id}>
                        <TableCell className="font-mono text-xs">{pr.sku_pattern}</TableCell>
                        <TableCell className="text-sm">
                          <div className="flex items-center gap-2">
                            <Sparkle size={12} className="text-yellow-400" weight="fill" />
                            {pr.nombre_comercial}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatCOP(pr.precio_promo, "COP")}
                          {pr.precio_lista > pr.precio_promo && (
                            <div className="text-[10px] text-zinc-500 line-through">
                              {formatCOP(pr.precio_lista, "COP")}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-zinc-400">
                          {(pr.bonos || []).join(" · ") || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  );
}
