// Planes de Zynex. `lista` es el precio sin código; `conCodigo` es lo que paga quien entra con el código de un socio (20 % menos, para siempre).
// `pago`: enlace de pago EN VIVO de Stripe. Vacío = todavía no se cobra por la app y el botón lleva a WhatsApp.
export const GRUPO_VIP = "https://chat.whatsapp.com/Gb9z8fWAiOwJ36dFp4FBDN";
export const WHATSAPP_VENTAS = "https://wa.me/573144644054";

export const PLANES = [
  { id: "os_inicio", nombre: "Logística Inicio", lista: 61, conCodigo: 48.8, incluye: "Pedidos, seguimiento, novedades y oficina", pago: "" },
  { id: "os_crecimiento", nombre: "Logística Crecimiento", lista: 186, conCodigo: 148.8, incluye: "Lo mismo, para más volumen", pago: "" },
  { id: "call", nombre: "Llamadas", lista: 124, conCodigo: 99.2, incluye: "Agentes de voz y 200 minutos al mes", pago: "" },
  { id: "paquete_inicio", nombre: "Logística Inicio + Llamadas", lista: 158, conCodigo: 126.4, incluye: "Las dos apps, 15 % menos que por separado", pago: "", paquete: true },
  { id: "paquete_crecimiento", nombre: "Logística Crecimiento + Llamadas", lista: 264, conCodigo: 211.2, incluye: "Las dos apps, 15 % menos que por separado", pago: "", paquete: true },
];

export const GRATIS = ["semáforo por ciudad", "ayuda dentro de la app", "grupo VIP de usuarios", "sesión de arranque"];
