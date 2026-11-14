/**
 * Instrucciones de cada pantalla y pestaña de Zynex OS.
 *
 * Una entrada por pantalla: { titulo, intro, pasos: [2..4], pideselo }.
 *  - `pideselo` es un ejemplo de lo que el usuario puede escribirle al
 *    asistente (Lyan por defecto) para que lo haga por él.
 *  - Textos neutrales al sector: sirven para una clínica, una tienda,
 *    una inmobiliaria o un restaurante.
 *
 * Layout.jsx pinta estas instrucciones automáticamente según la ruta
 * (ROUTE_HELP) o la pestaña activa (TAB_HELP). La prueba help.test.js falla
 * si una ruta o pestaña nueva se queda sin su entrada aquí.
 */
export const HELP = {
  // ---------------------------------------------------------------- públicas
  funnel: {
    titulo: "Bienvenida",
    intro: "Esta es la página de presentación. Explica qué hace Zynex OS, te deja probar el creador de agentes con un ejemplo y crear tu cuenta.",
    pasos: [
      "Prueba el ejemplo: elige una plantilla o escribe tu frase y pulsa «Ver el ejemplo».",
      "Pulsa «Crear mi agente gratis» si eres nuevo, o «Entrar» si ya tienes cuenta.",
      "Al entrar, el asistente te guía para dejar todo listo paso a paso.",
    ],
    pideselo: "Explícame en pocas palabras qué puedes hacer por mi negocio.",
  },
  login: {
    titulo: "Entrar",
    intro: "Aquí entras a tu cuenta con tu correo y tu contraseña.",
    pasos: [
      "Escribe el correo y la contraseña con los que te registraste.",
      "Pulsa «Entrar».",
      "Si aún no tienes cuenta, usa el enlace «Crear cuenta».",
    ],
    pideselo: "Ya entré. ¿Qué me falta configurar para empezar?",
  },
  register: {
    titulo: "Crear cuenta",
    intro: "Aquí creas tu cuenta y el espacio de tu empresa. Solo toma un minuto.",
    pasos: [
      "Escribe tu nombre, el nombre de tu empresa, tu correo y una contraseña.",
      "Pulsa «Crear cuenta».",
      "Al terminar te llevamos a los primeros pasos para configurar tu negocio.",
    ],
    pideselo: "Acabo de crear mi cuenta. Guíame paso a paso para dejarla lista.",
  },

  // ------------------------------------------------------------- principales
  copilot: {
    titulo: "Asistente",
    intro: "Aquí hablas con tu asistente. Le escribes lo que necesitas en palabras normales y él lo prepara. Antes de hacer cualquier cambio te muestra qué va a hacer y espera a que pulses «Aplicar».",
    pasos: [
      "Escribe lo que necesitas en el cuadro de abajo y pulsa Enter.",
      "Si el asistente propone una acción, revisa la tarjeta «quiere hacer esto».",
      "Pulsa «Aplicar» para que la haga o «Cancelar» para descartarla.",
      "Abre «Lo que hizo…» (la bitácora) para ver el registro de cada herramienta que usó.",
    ],
    pideselo: "Crea un agente que llame a mis clientes para recordarles su cita de mañana.",
  },
  dashboard: {
    titulo: "Resumen",
    intro: "Un vistazo rápido a cómo va tu operación hoy: cuántos pedidos o citas hay, cuántos se resolvieron y qué necesita tu atención.",
    pasos: [
      "Mira los números de arriba para saber cómo va el día.",
      "Revisa la lista de pendientes: lo más urgente aparece primero.",
      "Pulsa cualquier elemento para ver su detalle y actuar.",
    ],
    pideselo: "Dame un resumen de cómo va mi operación hoy y qué debo atender primero.",
  },
  pedidos: {
    titulo: "Pendientes",
    intro: "Aquí está todo lo que tienes por atender con tus clientes: la lista de pendientes y los casos abiertos.",
    pasos: [
      "Revisa la pestaña «Cola»: lo más urgente aparece arriba.",
      "Usa «Tickets» para dar seguimiento a los casos que necesitan a una persona.",
      "Si instalas un paquete (Ajustes → Perfil → Paquetes), aquí aparecen sus pestañas.",
    ],
    pideselo: "Muéstrame los pendientes más urgentes de hoy.",
  },
  metricas: {
    titulo: "Métricas",
    intro: "Los resultados de tu operación en números. Las cifras medidas van primero; las que dependen de supuestos llevan la etiqueta «Estimado» y muestran esos supuestos.",
    pasos: [
      "Empieza a operar: los números aparecen cuando hay actividad real.",
      "Mira las tres cifras principales para saber cómo vas.",
      "Si ves «Estimado», lee los supuestos (margen, tasa base, tipo de cambio) antes de usar la cifra.",
    ],
    pideselo: "Resume mis resultados de esta semana y dime qué puedo mejorar.",
  },
  conexiones: {
    titulo: "Conexiones",
    intro: "Aquí conectas las herramientas que ya usas (mensajería, telefonía, tu sistema de pedidos o citas). Tú pones tus propias llaves; se guardan cifradas y solo tu empresa las usa.",
    pasos: [
      "Elige la pestaña de lo que quieres conectar.",
      "Sigue las instrucciones de cada tarjeta y pega la llave que te da tu proveedor.",
      "Pulsa «Probar conexión»: verde significa listo; rojo, revisa la llave.",
      "Si tu proveedor pide una dirección de webhook, cópiala de «Tus direcciones de webhook».",
    ],
    pideselo: "Dime qué conexiones me faltan para que mi agente pueda llamar y escribir a mis clientes.",
  },
  ajustes: {
    titulo: "Ajustes",
    intro: "Lo que se configura una vez: los datos de tu negocio, tus agentes, tu catálogo y la forma en que el asistente habla con tus clientes.",
    pasos: [
      "Empieza por «Perfil» y completa los datos de tu negocio.",
      "En «Agentes» crea tu primer agente describiendo qué debe hacer.",
      "Revisa las demás pestañas cuando quieras afinar los detalles.",
    ],
    pideselo: "Revisa mi configuración y dime qué me falta completar.",
  },
  onboarding: {
    titulo: "Primeros pasos",
    intro: "Tres pasos para dejar tu cuenta lista: cuéntanos de tu negocio, conecta la inteligencia artificial y crea tu primer agente.",
    pasos: [
      "Completa el perfil de tu negocio (nombre, sector, país y moneda).",
      "Pega la llave de tu proveedor de inteligencia artificial y pruébala.",
      "Describe en una frase qué debe hacer tu primer agente y pulsa «Generar agente».",
    ],
    pideselo: "Ayúdame a configurar mi cuenta desde cero.",
  },

  // ------------------------------------------------------- pestañas: Pedidos
  queue: {
    titulo: "Cola",
    intro: "La lista de lo que tienes pendiente con tus clientes, ordenada por urgencia. El color indica cuánto tiempo queda para atender cada uno.",
    pasos: [
      "Rojo es urgente, amarillo es pronto y verde va con tiempo.",
      "Usa el buscador y los filtros para encontrar a un cliente.",
      "Pulsa la flecha de una fila para ver el detalle y el historial de contacto.",
    ],
    pideselo: "Muéstrame los pendientes en rojo y propón a quién contactar primero.",
  },
  import: {
    titulo: "Importar",
    intro: "Pantalla del paquete de contra entrega: sube el archivo de pedidos (Excel o CSV) y el sistema los carga por ti.",
    pasos: [
      "Elige el archivo desde tu computador o arrástralo al recuadro.",
      "Revisa la vista previa: verifica que nombres y teléfonos se lean bien.",
      "Pulsa «Importar». Los registros nuevos aparecen en la Cola.",
    ],
    pideselo: "Voy a subir un archivo con mis pedidos. Dime qué columnas necesita.",
  },
  novedades: {
    titulo: "Novedades",
    intro: "Pantalla del paquete de contra entrega: los avisos de las empresas de envío (un retraso, un intento fallido) y qué hace el sistema con cada uno.",
    pasos: [
      "Cada fila es un tipo de aviso y la acción que se toma.",
      "Revisa que la acción sea la que quieres para tu negocio.",
      "Si algo no encaja, pide el cambio al asistente.",
    ],
    pideselo: "Explícame qué avisos llegaron hoy y qué se hizo con cada uno.",
  },
  tasks: {
    titulo: "Tickets",
    intro: "Los casos que necesitan a una persona de tu equipo: una duda del cliente, un reclamo o algo que el agente no pudo resolver solo.",
    pasos: [
      "Pulsa «Nuevo» para crear un caso a mano, o deja que el agente los cree.",
      "Filtra por estado para ver solo los abiertos.",
      "Marca el caso como resuelto cuando lo cierres.",
    ],
    pideselo: "Crea un ticket para llamar mañana al cliente que pidió cambiar su cita.",
  },
  messages: {
    titulo: "Mensajes",
    intro: "El registro de los mensajes enviados y recibidos con tus clientes, para que sepas qué se dijo y cuándo.",
    pasos: [
      "Busca por nombre o teléfono para encontrar una conversación.",
      "Revisa el estado de cada mensaje: enviado, entregado o con error.",
      "Si un mensaje falló, verifica la conexión de mensajería en Conexiones.",
    ],
    pideselo: "Muéstrame los mensajes que fallaron hoy y por qué.",
  },

  // ---------------------------------------------------- pestañas: Conexiones
  connectors: {
    titulo: "Conectores",
    intro: "Las herramientas que puedes enlazar con tu cuenta: mensajería, telefonía, voz y tu tienda. Tú pones tus llaves y le pagas a cada proveedor lo que uses.",
    pasos: [
      "Elige una tarjeta y abre sus instrucciones.",
      "Pega los datos que te da ese proveedor.",
      "Pulsa «Probar conexión» para confirmar que quedó bien.",
      "Abajo, en «Tus direcciones de webhook», copia la dirección que te pida cada proveedor.",
    ],
    pideselo: "¿Qué conector necesito para enviar mensajes de WhatsApp a mis clientes?",
  },
  mcp: {
    titulo: "Conectores MCP",
    intro: "Un conector MCP es una dirección web que le da al asistente herramientas nuevas (por ejemplo, tu calendario o tu sistema de inventario). Conecta solo servidores en los que confíes.",
    pasos: [
      "Escribe un nombre y la dirección (debe empezar por https://).",
      "Si el servidor pide clave, elige el tipo de autenticación y pégala.",
      "Pulsa «Probar conexión» para ver las herramientas disponibles.",
      "Activa solo las que necesites. Si una herramienta cambia, se desactiva sola y te avisamos.",
    ],
    pideselo: "¿Qué herramientas nuevas tienes disponibles gracias a mis conectores MCP?",
  },
  config: {
    titulo: "Credenciales",
    intro: "Aquí guardas las llaves de tus proveedores. Se cifran al guardarlas y nunca se vuelven a mostrar completas.",
    pasos: [
      "Busca el proveedor y pega tu llave en su campo.",
      "Pulsa «Guardar» y luego «Probar» para confirmar que funciona.",
      "Para cambiarla, pega la nueva encima. Para quitarla, pulsa «Borrar».",
    ],
    pideselo: "¿Qué llaves tengo configuradas y cuáles me faltan?",
  },
  voices: {
    titulo: "Voces",
    intro: "Las voces que usan tus agentes cuando llaman. Puedes tener una distinta por país o por tipo de llamada.",
    pasos: [
      "Agrega una voz con el identificador que te da tu proveedor de voz.",
      "Escúchala para confirmar que suena como quieres.",
      "Márcala como predeterminada para el país que corresponda.",
    ],
    pideselo: "Recomiéndame una voz cálida y profesional para llamar a mis clientes.",
  },
  numbers: {
    titulo: "Números",
    intro: "Los números de teléfono desde los que llaman tus agentes. Deben estar verificados para que el cliente vea un número conocido.",
    pasos: [
      "Agrega tu número con el código de país (por ejemplo +57…).",
      "Sigue la verificación: recibirás una llamada o un código.",
      "Cuando aparezca como verificado, ya puedes usarlo en tus agentes.",
    ],
    pideselo: "¿Qué número tengo verificado para hacer llamadas?",
  },

  // ------------------------------------------------------- pestañas: Ajustes
  perfil: {
    titulo: "Perfil",
    intro: "Tus datos y los de tu negocio. El asistente usa el perfil del negocio (sector, país, moneda, idioma) para adaptarse a tu empresa.",
    pasos: [
      "Completa el perfil del negocio y pulsa «Guardar perfil».",
      "Si quieres, cambia el nombre del asistente.",
      "Actualiza tu foto, tu nombre o tu contraseña cuando lo necesites.",
      "En «Paquetes» instala funciones opcionales (por ejemplo, contra entrega): sus pantallas aparecen al instalarlas.",
    ],
    pideselo: "Actualiza el perfil de mi negocio: somos una clínica dental en México y trabajamos en pesos mexicanos.",
  },
  agentes: {
    titulo: "Agentes",
    intro: "Un agente es un asistente que llama o escribe a tus clientes para una tarea concreta: recordar una cita, confirmar un pedido, avisar de un pago. Lo creas describiendo tu negocio en una frase.",
    pasos: [
      "Escribe qué hace tu negocio y qué debe hacer el agente, o elige una plantilla.",
      "Pulsa «Generar agente» y revisa la propuesta: puedes cambiar cualquier texto.",
      "Pulsa «Aplicar y guardar». Nada se guarda como definitivo hasta entonces.",
      "Completa lo que falte (voz y número) y haz una llamada de prueba.",
    ],
    pideselo: "Crea un agente para mi restaurante que confirme las reservas del día por teléfono.",
  },
  llamadas: {
    titulo: "Llamadas",
    intro: "El historial de las llamadas que hicieron tus agentes: con quién hablaron, cuánto duró, qué se dijo y cómo terminó.",
    pasos: [
      "Cada fila es una llamada. Pulsa una para ver la conversación escrita.",
      "Escucha la grabación si necesitas confirmar algo.",
      "Usa lo que escuches para mejorar el guion del agente.",
    ],
    pideselo: "Resume las llamadas de hoy y dime cuántas terminaron bien.",
  },
  products: {
    titulo: "Productos",
    intro: "Tu catálogo de productos o servicios, con precio y promociones. Los agentes lo usan para responder preguntas de tus clientes.",
    pasos: [
      "Pulsa «Nuevo producto» y escribe nombre, precio y una descripción corta.",
      "Agrega una promoción si quieres que el agente la mencione.",
      "Edita o elimina cuando cambien tus precios.",
    ],
    pideselo: "Agrega a mi catálogo el servicio «Limpieza dental» con precio 80.",
  },
  prompts: {
    titulo: "Guiones",
    intro: "El guion es lo que el agente dice y cómo lo dice. Aquí lo ajustas por país o por tipo de conversación.",
    pasos: [
      "Elige el guion que quieres revisar.",
      "Cambia el texto con tus palabras: tono, saludo y lo que no debe decir.",
      "Guarda y haz una prueba antes de usarlo con clientes.",
    ],
    pideselo: "Haz que el saludo de mi agente suene más cercano y menos formal.",
  },
  cadence: {
    titulo: "Cadencia",
    intro: "Pantalla del paquete de contra entrega: cuántas veces y a qué horas se intenta contactar al cliente de cada pedido.",
    pasos: [
      "Revisa los intentos programados y su horario.",
      "Ajusta días, horas y canal (llamada o mensaje) según tu negocio.",
      "Guarda. Los próximos contactos seguirán el plan nuevo.",
    ],
    pideselo: "Configura tres intentos de contacto: mañana, tarde y al día siguiente.",
  },
  carriers: {
    titulo: "Transportadoras",
    intro: "Pantalla del paquete de contra entrega: las empresas de envío con las que trabajas y los plazos de cada una.",
    pasos: [
      "Revisa la lista y los plazos de cada empresa de envío.",
      "Confirma que coincidan con tus acuerdos reales.",
      "Si algo no coincide, pide el cambio al asistente.",
    ],
    pideselo: "¿Qué plazos tengo configurados para cada empresa de envío?",
  },
  skills: {
    titulo: "Habilidades",
    intro: "Una habilidad es una instrucción guardada que el asistente puede repetir cuando se la pidas, como «informe semanal».",
    pasos: [
      "Pulsa «Nueva» y dale un nombre corto.",
      "Escribe las instrucciones como se las dirías a una persona.",
      "Úsala desde el asistente eligiéndola en la lista de habilidades.",
    ],
    pideselo: "Crea una habilidad que me prepare un informe semanal de resultados.",
  },
  vipLeads: {
    titulo: "Clientes VIP",
    intro: "Las personas interesadas que merecen atención prioritaria. Aquí las ves juntas para que nadie se quede sin respuesta.",
    pasos: [
      "Revisa la lista: los más recientes aparecen primero.",
      "Abre uno para ver sus datos y lo que pidió.",
      "Márcalo como contactado cuando lo atiendas.",
    ],
    pideselo: "Muéstrame los interesados VIP que aún no hemos contactado.",
  },
};

/** Ruta real (definida en App.js) → clave de HELP. */
export const ROUTE_HELP = {
  "/": "funnel",
  "/funnel": "funnel",
  "/login": "login",
  "/register": "register",
  "/app": "copilot",
  "/app/pedidos": "pedidos",
  "/app/conexiones": "conexiones",
  "/app/metricas": "metricas",
  "/app/ajustes": "ajustes",
  "/app/onboarding": "onboarding",
};

/** Contenedor de pestañas → { clave de pestaña → clave de HELP }. */
export const TAB_HELP = {
  pedidos: {
    cola: "queue",
    importar: "import",
    novedades: "novedades",
    tickets: "tasks",
  },
  conexiones: {
    conectores: "connectors",
    mcp: "mcp",
    credenciales: "config",
    voces: "voices",
    numeros: "numbers",
  },
  ajustes: {
    perfil: "perfil",
    agentes: "agentes",
    llamadas: "llamadas",
    productos: "products",
    prompts: "prompts",
    cadencia: "cadence",
    transportadoras: "carriers",
    habilidades: "skills",
    vip: "vipLeads",
  },
};

/** Archivo de src/pages (sin extensión) → clave de HELP. */
export const PAGE_HELP = {
  Dashboard: "dashboard", Pedidos: "pedidos", Queue: "queue", Cadence: "cadence",
  Tasks: "tasks", Import: "import", Messages: "messages", Novedades: "novedades",
  Carriers: "carriers", Products: "products", Prompts: "prompts", Skills: "skills",
  Voices: "voices", Numbers: "numbers", VipLeads: "vipLeads", Connectors: "connectors",
  Config: "config", Conexiones: "conexiones", Agentes: "agentes", Llamadas: "llamadas",
  Metricas: "metricas", Copilot: "copilot", Ajustes: "ajustes", Perfil: "perfil",
  Onboarding: "onboarding", Login: "login", Register: "register", Funnel: "funnel",
};

export function helpForRoute(pathname) {
  const clean = (pathname || "/").replace(/\/+$/, "") || "/";
  return ROUTE_HELP[clean] || null;
}

export function helpForTab(hub, tab) {
  return (TAB_HELP[hub] || {})[tab] || null;
}

/** Enlace al asistente con el texto ya escrito en el cuadro. */
export function copilotPromptUrl(prompt) {
  return `/app?prompt=${encodeURIComponent(prompt || "")}`;
}
