import { useEffect, useRef, useState } from "react";

/** Lyan en 3D dentro de una caja (login, registro, tarjetas). Si el navegador no tiene 3D, muestra su imagen.
 *  `onEstado(nombre)` avisa cuando cambia entre vigila, novedad y resuelto, para que la página cambie de color con ella. */
export default function Lyan3D({ className = "", onEstado }) {
  const lienzo = useRef(null);
  const [plano, setPlano] = useState(false);
  useEffect(() => {
    let escena, vivo = true;
    import("../three/escenaLyan").then(({ montar }) => {
      if (!vivo || !lienzo.current) return;
      escena = montar(lienzo.current, { modo: "retrato", onEstado, onError: () => vivo && setPlano(true) });
      if (!escena) setPlano(true);
    }).catch(() => vivo && setPlano(true));
    return () => { vivo = false; escena?.destruir(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (plano) return <img src="/lyan.webp" alt="" className={className} style={{ objectFit: "contain" }} />;
  return <canvas ref={lienzo} className={className} aria-hidden="true" data-testid="lyan-3d" />;
}
