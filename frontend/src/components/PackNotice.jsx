import { Link } from "react-router-dom";
import { Package } from "@phosphor-icons/react";

/** Aviso cuando se abre una pantalla que pertenece a un paquete no instalado. */
export default function PackNotice({ nombre = "Contra entrega (Colombia)" }) {
  return (
    <div className="border border-zinc-800 bg-zinc-900/40 rounded-sm p-6 max-w-2xl" data-testid="pack-notice">
      <div className="flex items-center gap-2 mb-2">
        <Package size={18} weight="duotone" className="text-zinc-400" />
        <h3 className="text-lg font-medium text-zinc-200">Esta pantalla es del paquete «{nombre}»</h3>
      </div>
      <p className="text-sm text-zinc-400 leading-relaxed mb-4">
        Tu cuenta no lo tiene instalado, y no lo necesitas para crear agentes, llamar o escribir a tus
        clientes. Si tu operación lo requiere, puedes instalarlo cuando quieras.
      </p>
      <Link to="/app/ajustes?tab=perfil" reloadDocument
            data-testid="pack-notice-link"
            className="inline-flex items-center h-9 px-4 rounded-sm border border-zinc-700 bg-zinc-950 text-sm text-zinc-200 hover:bg-zinc-800 hover:text-white transition">
        Ver paquetes en Perfil
      </Link>
    </div>
  );
}
