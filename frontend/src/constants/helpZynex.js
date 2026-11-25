/**
 * Instrucciones de las pantallas de Zynex para ventas contra entrega
 * (Logística, Clientes, Agente de Voz y Encuesta). Se suman a help.js al
 * cargar la app: cada pantalla dice para qué sirve y cómo funciona.
 */
import { HELP, ROUTE_HELP, TAB_HELP, PAGE_HELP } from "./help";

Object.assign(HELP, {
  logistica: {
    titulo: "Agente de Logística",
    intro: "Sirve para que ningún pedido de Dropi se quede sin gestionar: confirma, avisa novedades y recuerda los pedidos en oficina. Lee tus pedidos cada 30 segundos y decide qué hacer con cada uno según su estado.",
    pasos: [
      "En «Panel» ves cuántos pedidos hay en cada estado. Toca un número y se abre la lista de esos pedidos.",
      "En «Métricas» ves cómo va la operación: tasa de entrega, plata por rescatar y entrega por transportadora.",
      "En «Plantillas» escribes el nombre de tu plantilla de WhatsApp en cada casilla. Tú eliges el texto.",
      "En «Secuencia» ves el orden para cada estado: mensaje, llamada y WhatsApp de seguimiento.",
    ],
    pideselo: "Muéstrame los pedidos que llevan más días en oficina.",
  },
  clientes: {
    titulo: "Clientes · Sofía",
    intro: "Sirve para conocer a cada cliente y atenderlo bien: junta todos los pedidos de un mismo teléfono en una sola ficha, con sus notas y con la lista de quienes necesitan a una persona.",
    pasos: [
      "Toca un número de arriba para filtrar: quienes necesitan a una persona, quienes ya compraron dos veces o quienes han devuelto.",
      "Busca por nombre, teléfono o ciudad y toca el nombre para abrir la ficha.",
      "En la ficha deja notas para el equipo y marca «Que lo atienda una persona» si es un reclamo, plata o un cliente molesto.",
      "Cuando quede atendido, pulsa «Ya quedó resuelto» y sale de la bandeja.",
    ],
    pideselo: "Dime qué clientes necesitan que los atienda una persona hoy.",
  },
  claudeTab: {
    titulo: "Claude",
    intro: "Sirve para manejar tu negocio desde tu propio Claude: le pides en palabras normales que revise pedidos, llamadas o resultados y él lo hace con tus datos.",
    pasos: [
      "Copia la dirección del conector que aparece aquí.",
      "En Claude, abre Conectores, agrega uno nuevo y pega esa dirección.",
      "Pídele a Claude lo que necesites, por ejemplo los pedidos en oficina de hoy.",
    ],
    pideselo: "Explícame cómo conectar mi Claude con Zynex paso a paso.",
  },
  zynexCall: {
    titulo: "Agente de Voz",
    intro: "Sirve para llamar a los clientes que no respondieron el mensaje. Cada estado de Dropi tiene su agente de voz con su guion.",
    pasos: [
      "Revisa qué agente atiende cada estado: confirmación, novedad y oficina.",
      "Ajusta el guion y la voz de cada agente antes de activarlo.",
      "Las llamadas solo salen cuando tú las enciendes y dentro del horario permitido.",
    ],
    pideselo: "Explícame qué dice el agente de voz cuando un pedido está en oficina.",
  },
  encuesta: {
    titulo: "Encuesta a dropshippers",
    intro: "Sirve para saber qué le duele más a quien vende con Dropi antes de decidir qué construir. Aquí ves las respuestas del formulario público.",
    pasos: [
      "Copia el enlace y compártelo en tus grupos. Agrega «?origen=nombre-del-grupo» para saber de dónde llegó cada respuesta.",
      "Mira los totales y las barras: muestran qué problema se repite más.",
      "Toca una barra para ver solo las respuestas que la forman.",
    ],
    pideselo: "Resume las respuestas de la encuesta y dime el problema más repetido.",
  },
  encuestaPublica: {
    titulo: "Encuesta",
    intro: "Formulario público de dos minutos para quienes venden con Dropi. No pide iniciar sesión.",
    pasos: [
      "Responde las cuatro preguntas obligatorias.",
      "Si quieres la prueba gratis, deja tu WhatsApp y acepta que te escribamos.",
      "Pulsa «Enviar respuestas».",
    ],
    pideselo: "Explícame para qué sirve esta encuesta.",
  },
});

Object.assign(ROUTE_HELP, {
  "/app/logistica": "logistica",
  "/app/clientes": "clientes",
  "/app/llamadas": "zynexCall",
  "/app/encuesta": "encuesta",
  "/encuesta": "encuestaPublica",
});

Object.assign(TAB_HELP.conexiones, { claude: "claudeTab" });

Object.assign(PAGE_HELP, {
  Logistica: "logistica", Clientes: "clientes", ZynexCall: "zynexCall",
  Encuesta: "encuestaPublica", EncuestaResultados: "encuesta",
});
