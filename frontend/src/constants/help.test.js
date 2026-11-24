/**
 * Falla si alguna pantalla, ruta o pestaña se queda sin instrucciones.
 * Lee App.js y los contenedores de pestañas como texto: no hace falta
 * renderizar nada, así la prueba es rápida y no depende del backend.
 */
import fs from "fs";
import path from "path";
import { HELP, ROUTE_HELP, TAB_HELP, PAGE_HELP, helpForRoute, helpForTab } from "./help";

const SRC = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

// Contenedores de pestañas: archivo → clave en TAB_HELP.
const HUBS = { "pages/Pedidos.jsx": "pedidos", "pages/Conexiones.jsx": "conexiones", "pages/Ajustes.jsx": "ajustes" };

/** Rutas de App.js que pintan una pantalla (las que solo redirigen no cuentan). */
function declaredRoutes() {
  const out = [];
  const re = /<Route\s+path="([^"]+)"\s+element=\{([^\n]+)\}\s*\/>/g;
  let m;
  const src = read("App.js");
  while ((m = re.exec(src))) {
    if (m[1] === "*" || m[2].includes("<Navigate")) continue;
    out.push(m[1]);
  }
  return out;
}

/** Claves de pestaña declaradas en el arreglo TABS de un contenedor. */
function declaredTabs(file) {
  const src = read(file);
  const block = src.slice(src.indexOf("const TABS = ["), src.indexOf("];", src.indexOf("const TABS = [")));
  return [...block.matchAll(/\{\s*key:\s*"([^"]+)"/g)].map((m) => m[1]);
}

describe("help.js — instrucciones de todas las pantallas", () => {
  test("cada entrada tiene título, intro, 2 a 4 pasos y un ejemplo para pedírselo al asistente", () => {
    Object.entries(HELP).forEach(([key, h]) => {
      expect({ key, titulo: typeof h.titulo }).toEqual({ key, titulo: "string" });
      expect(h.titulo.trim().length).toBeGreaterThan(0);
      expect(h.intro.trim().length).toBeGreaterThan(20);
      expect(Array.isArray(h.pasos)).toBe(true);
      expect({ key, pasos: h.pasos.length >= 2 && h.pasos.length <= 4 }).toEqual({ key, pasos: true });
      h.pasos.forEach((p) => expect(p.trim().length).toBeGreaterThan(5));
      expect({ key, pideselo: (h.pideselo || "").trim().length > 10 }).toEqual({ key, pideselo: true });
    });
  });

  test("cada ruta declarada en App.js tiene instrucciones", () => {
    const routes = declaredRoutes();
    expect(routes.length).toBeGreaterThanOrEqual(8);
    const missing = routes.filter((r) => !HELP[helpForRoute(r)]);
    expect(missing).toEqual([]);
  });

  test("ROUTE_HELP no apunta a rutas que ya no existen ni a claves inexistentes", () => {
    const routes = declaredRoutes();
    Object.entries(ROUTE_HELP).forEach(([route, key]) => {
      expect({ route, declared: routes.includes(route) }).toEqual({ route, declared: true });
      expect({ route, hasHelp: !!HELP[key] }).toEqual({ route, hasHelp: true });
    });
  });

  test("cada pestaña declarada en los contenedores tiene instrucciones", () => {
    Object.entries(HUBS).forEach(([file, hub]) => {
      const tabs = declaredTabs(file);
      expect(tabs.length).toBeGreaterThan(0);
      const missing = tabs.filter((t) => !HELP[helpForTab(hub, t)]);
      expect({ hub, missing }).toEqual({ hub, missing: [] });
      // y al revés: TAB_HELP no conserva pestañas borradas
      const stale = Object.keys(TAB_HELP[hub]).filter((t) => !tabs.includes(t));
      expect({ hub, stale }).toEqual({ hub, stale: [] });
    });
  });

  test("cada página de src/pages (salvo AuthCallback) tiene instrucciones", () => {
    const pages = fs.readdirSync(path.join(SRC, "pages"))
      .filter((f) => /\.jsx?$/.test(f) && !/\.test\./.test(f))
      .map((f) => f.replace(/\.jsx?$/, ""))
      .filter((n) => n !== "AuthCallback");
    expect(pages.length).toBeGreaterThanOrEqual(28);
    const missing = pages.filter((n) => !HELP[PAGE_HELP[n]]);
    expect(missing).toEqual([]);
  });

  test("Base de conocimiento y Automatizaciones son pestañas de Ajustes con instrucciones y estado vacío", () => {
    const tabs = declaredTabs("pages/Ajustes.jsx");
    [["conocimiento", "kb", "components/KnowledgeBase.jsx"],
     ["automatizaciones", "automations", "components/Automations.jsx"]].forEach(([tab, key, file]) => {
      expect({ tab, declared: tabs.includes(tab) }).toEqual({ tab, declared: true });
      expect({ tab, key: helpForTab("ajustes", tab) }).toEqual({ tab, key });
      expect(HELP[key].pasos.length).toBeGreaterThanOrEqual(2);
      expect(read("pages/Ajustes.jsx")).toMatch(new RegExp(`tab === "${tab}"`));
      expect(read(file)).toMatch(/<EmptyState/);
    });
  });

  test("las pestañas exclusivas de contra entrega declaran su paquete (se ocultan si no está instalado)", () => {
    const packTabs = { "pages/Pedidos.jsx": ["importar", "novedades"], "pages/Ajustes.jsx": ["cadencia", "transportadoras"] };
    Object.entries(packTabs).forEach(([file, keys]) => {
      const src = read(file);
      expect(src).toMatch(/usePacks\(/);
      keys.forEach((k) => {
        const line = src.split("\n").find((l) => l.includes(`key: "${k}"`)) || "";
        expect({ file, k, pack: /pack:\s*"cod_colombia"/.test(line) }).toEqual({ file, k, pack: true });
      });
    });
  });

  test("fuera de las pantallas del paquete no quedan textos de un cliente o sector concreto", () => {
    const PACK_SCREENS = ["pages/Import.jsx", "pages/Novedades.jsx", "pages/Cadence.jsx", "pages/Carriers.jsx"];
    const banned = /litper|antifluido|sof[ií]a|emergent/i;
    const walk = (dir) => fs.readdirSync(path.join(SRC, dir), { withFileTypes: true }).flatMap((d) => {
      const rel = path.posix.join(dir, d.name);
      if (d.isDirectory()) return walk(rel);
      return /\.(jsx?|css)$/.test(d.name) && !/\.test\./.test(d.name) ? [rel] : [];
    });
    const hits = walk(".").filter((f) => !PACK_SCREENS.includes(f) && banned.test(read(f)));
    expect(hits).toEqual([]);
  });

  test("los contenedores y Layout pintan las instrucciones desde help.js (sin textos duplicados a mano)", () => {
    expect(read("components/Layout.jsx")).toMatch(/PageHelp/);
    Object.keys(HUBS).forEach((file) => {
      const src = read(file);
      expect(src).toMatch(/helpForTab\(/);
      expect(src).not.toMatch(/<HowItWorks/);
    });
    fs.readdirSync(path.join(SRC, "pages")).forEach((f) => {
      expect({ f, manual: /<HowItWorks/.test(read(`pages/${f}`)) }).toEqual({ f, manual: false });
    });
  });
});
