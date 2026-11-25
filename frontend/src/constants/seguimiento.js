/**
 * Seguimiento logístico de un pedido COD con Dropi: en qué etapa va, qué toca hacer
 * y dónde rastrearlo. Reglas tomadas de la cadena de seguimiento logístico probada en operación real
 * (rastreo, bodega, reparto, oficina, novedad, devolución) para cualquier tienda.
 */
const GRUPOS = [
  [["PENDIENTE CONFIRMACION", "PENDIENTE", "TELEMERCADEO"], "CONFIRMAR"],
  [["GUIA_GENERADA", "EN PROCESAMIENTO", "PREPARADO PARA TRANSPORTADORA"], "SIN_RECOLECTAR"],
  [["EN TERMINAL DESTINO", "EN BODEGA DESTINO"], "BODEGA_DESTINO"],
  [["EN REPARTO"], "REPARTO"],
  [["RECLAME EN OFICINA", "EN PUNTO DROOP"], "OFICINA"],
  [["NOVEDAD", "INTENTO DE ENTREGA", "NOVEDAD SOLUCIONADA", "REENVIO"], "NOVEDAD"],
  [["EN REEXPEDICION", "EN PROCESO DE INDEMNIZACION"], "DEVOLUCION"],
  [["DEVOLUCION"], "DEVUELTO"],
  [["ENTREGADO"], "ENTREGADO"],
  [["CANCELADO", "RECHAZADO"], "CERRADO"],
];

export const ETAPA = {
  CONFIRMAR: { nombre: "Por confirmar", paso: 1, que: "Confirmar producto, dirección y valor. Si falta un dato, pasa a Pendientes diarios." },
  SIN_RECOLECTAR: { nombre: "Guía sin recolectar", paso: 2, que: "Vigilar que la transportadora lo recoja. Si pasa un día sin recolección, es despacho tardío: revisar con Dropi." },
  TRANSITO: { nombre: "En tránsito", paso: 3, que: "Nada al cliente. Vigilar que se mueva: más de 24 horas quieto se abre ticket en Dropi «Órdenes sin movimiento», con pantallazo de la transportadora." },
  BODEGA_DESTINO: { nombre: "En bodega de destino", paso: 4, que: "Avisar al cliente que llegó a su ciudad. Hoy o mañana sale a reparto u oficina." },
  REPARTO: { nombre: "En reparto", paso: 5, que: "Avisar antes de las 10 a.m. que va en camino y clasificar lo que responda. Un solo aviso por día." },
  OFICINA: { nombre: "Para reclamar en oficina", paso: 5, que: "Avisar dirección de la oficina y plazo, y recordar cada día. A los 7 días lo llama una persona. Nunca ofrecer llevarlo a la casa." },
  NOVEDAD: { nombre: "Con novedad", paso: 5, que: "Entender qué pasó, coordinar un nuevo intento con el cliente (la transportadora da 3) y dejar la solución en Dropi." },
  DEVOLUCION: { nombre: "Devolviéndose", paso: 5, que: "No avisar reparto. Intentar salvarlo antes de que regrese; el reenvío con condiciones lo ofrece una persona." },
  DEVUELTO: { nombre: "Devuelto", paso: 6, que: "Ofrecer reenvío con condiciones o descartarlo. Lo decide una persona." },
  ENTREGADO: { nombre: "Entregado", paso: 6, que: "Cerrar: quitar etiquetas y pausas. Es buen momento para recompra." },
  CERRADO: { nombre: "Cancelado o rechazado", paso: 6, que: "Sin acción logística. Revisar el motivo si se repite en la misma ciudad." },
};

export function grupoLogistico(estado) {
  const e = String(estado || "").trim().toUpperCase();
  const g = GRUPOS.find(([lista]) => lista.includes(e));
  return g ? g[1] : "TRANSITO";
}

/** Alertas que piden mirar el pedido ya (días = días en el estado actual). */
export function alertas(grupo, dias) {
  const d = Number(dias) || 0;
  const a = [];
  if ((grupo === "TRANSITO" || grupo === "SIN_RECOLECTAR") && d >= 1) a.push({ txt: `${d} días sin moverse: abre ticket en Dropi «Órdenes sin movimiento».`, persona: false });
  if (grupo === "OFICINA" && d >= 7) a.push({ txt: `${d} días en oficina: llamada de una persona antes de que se devuelva.`, persona: true });
  else if (grupo === "OFICINA" && d >= 4) a.push({ txt: `${d} días en oficina: recordatorio diario, quedan pocos días.`, persona: false });
  if (grupo === "NOVEDAD" && d >= 2) a.push({ txt: `${d} días con novedad: sin solución la transportadora lo devuelve.`, persona: false });
  if (grupo === "DEVOLUCION" || grupo === "DEVUELTO") a.push({ txt: "Devolución: lo atiende una persona.", persona: true });
  if (grupo === "CONFIRMAR" && d >= 1) a.push({ txt: `${d} días sin confirmar: pasa a Pendientes finales.`, persona: false });
  return a;
}

/** Transportadora por nombre o, si no viene, por el formato de la guía. */
export function transportadoraDe(nombre, guia) {
  const n = String(nombre || "").toUpperCase();
  const g = String(guia || "");
  if (n.includes("INTER") || /^240\d{9}$/.test(g)) return "INTERRAPIDISIMO";
  if (n.includes("ENVIA") || /^(014|114)\d{9}$/.test(g)) return "ENVIA";
  if (n.includes("COORDI") || /^(99360|36396|36397)\d{6}$/.test(g)) return "COORDINADORA";
  if (n.includes("TCC") || /^617\d{6}$/.test(g)) return "TCC";
  return n || "";
}

/** Página para rastrear la guía en la transportadora (manda sobre Dropi). */
export function rastreo(nombre, guia) {
  if (!guia) return null;
  const g = encodeURIComponent(String(guia));
  switch (transportadoraDe(nombre, guia)) {
    case "INTERRAPIDISIMO": return { url: `https://t.17track.net/es#nums=${g}&fc=100491`, txt: "Rastrear en Interrapidísimo" };
    case "ENVIA": return { url: `https://envia.co/rastreo?guia=${g}`, txt: "Rastrear en Envía" };
    case "COORDINADORA": return { url: "https://coordinadora.com/rastreo/rastreo-guias-multiples/", txt: "Rastrear en Coordinadora (pega la guía)" };
    case "TCC": return { url: "https://tcc.com.co", txt: "Rastrear en TCC (pega la guía)" };
    default: return null;
  }
}
