// Escena 3D de Zynex: Lyan en su torre de control.
// Lyan no está de adorno: vigila las rutas, se voltea hacia el pedido que entra en novedad (todo se pone ámbar),
// lo resuelve (verde) y celebra. Saluda al llegar y responde al clic. Todo lo que se mueve es decoración: sin datos de nadie.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const NOCHE = { fondo: 0x04070c, niebla: 0x04070c, glifo: [0.10, 0.78, 1.0], suelo: 0x070b12, luz: 1.0 };
const DIA = { fondo: 0xe9f1f8, niebla: 0xe9f1f8, glifo: [0.02, 0.36, 0.55], suelo: 0xdbe6f0, luz: 1.9 };
// Estados de trabajo de Lyan y su color (noche, día).
export const ESTADOS = {
  vigila: { noche: 0x19c8ff, dia: 0x0369a1, css: "#19c8ff", cssDia: "#0369a1" },
  novedad: { noche: 0xffb020, dia: 0xb45309, css: "#ffb020", cssDia: "#b45309" },
  resuelto: { noche: 0x34e3a0, dia: 0x047857, css: "#34e3a0", cssDia: "#047857" },
};
const CAJA = [0x19c8ff, 0xffb020, 0x34e3a0];

// Recorrido de la cámara según el avance de la página (0 a 1). Solo en modo "inicio".
const CAMARA = [
  { p: 0.0, pos: [-1.5, 1.55, 5.4], mira: [-1.5, 1.15, 0] },
  { p: 0.28, pos: [5.6, 2.6, 6.8], mira: [0, 1.0, 0] },
  { p: 0.55, pos: [0.5, 8.5, 8.5], mira: [0, 0.4, 0] },
  { p: 0.8, pos: [-5.8, 2.2, 6.2], mira: [0, 1.1, 0] },
  { p: 1.0, pos: [0, 1.5, 4.6], mira: [0, 1.2, 0] },
];

function atlasDeGlifos() {
  const c = document.createElement("canvas"); c.width = 512; c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = "#000"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#fff"; g.font = "600 46px 'IBM Plex Mono', ui-monospace, monospace"; g.textAlign = "center"; g.textBaseline = "middle";
  const letras = "0123456789ZYNEX#>/+=<:*%".split("").concat(["▢", "◇", "⬡", "→", "↯", "⟡", "▤", "∎"]);
  for (let i = 0; i < 64; i++) g.fillText(letras[i % letras.length], (i % 8) * 64 + 32, Math.floor(i / 8) * 64 + 34);
  const t = new THREE.CanvasTexture(c); t.minFilter = THREE.LinearFilter; t.generateMipmaps = false;
  return t;
}

/**
 * modo "inicio": lienzo a pantalla completa, cámara guiada por el scroll.
 * modo "retrato": lienzo del tamaño de su caja, cámara fija de frente (login, registro, tarjetas).
 */
export function montar(canvas, { modelo = "/lyan3d.glb", modo = "inicio", onProgreso, onListo, onError, onEstado } = {}) {
  const quieto = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const retrato = modo === "retrato";
  const ancho = () => (retrato ? canvas.clientWidth || 300 : window.innerWidth);
  const alto = () => (retrato ? canvas.clientHeight || 300 : window.innerHeight);
  const movil = ancho() < 720;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: !movil, alpha: retrato, powerPreference: "high-performance" }); }
  catch (e) { onError?.(e); return null; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, movil ? 1.5 : 1.75));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const escena = new THREE.Scene();
  escena.fog = new THREE.Fog(NOCHE.niebla, 9, 30);
  const camara = new THREE.PerspectiveCamera(movil && !retrato ? 52 : 40, 1, 0.1, 80);
  const mira = new THREE.Vector3();

  const ambiente = new THREE.HemisphereLight(0x9fd8ff, 0x05070b, 0.8);
  const frente = new THREE.DirectionalLight(0xdff4ff, 2.2); frente.position.set(-3, 5, 6);
  const contra = new THREE.PointLight(0x7c5cff, 26, 16); contra.position.set(3.2, 3.2, -3.5);
  const base = new THREE.PointLight(0x19c8ff, 14, 9); base.position.set(0, 0.25, 1.2);
  escena.add(ambiente, frente, contra, base);

  // Plataforma hexagonal.
  const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(1.75, 1.95, 0.22, 6), new THREE.MeshStandardMaterial({ color: NOCHE.suelo, metalness: 0.7, roughness: 0.35 }));
  cuerpo.position.y = -0.11;
  const matLinea = new THREE.MeshBasicMaterial({ color: 0x19c8ff, transparent: true, opacity: 0.95 });
  const borde = new THREE.Mesh(new THREE.TorusGeometry(1.78, 0.022, 8, 6), matLinea);
  borde.rotation.x = Math.PI / 2; borde.rotation.z = Math.PI / 6; borde.position.y = 0.012;
  const matLinea2 = new THREE.MeshBasicMaterial({ color: 0x19c8ff, transparent: true, opacity: 0.35 });
  const borde2 = new THREE.Mesh(new THREE.TorusGeometry(2.6, 0.008, 6, 6), matLinea2);
  borde2.rotation.copy(borde.rotation); borde2.position.y = -0.2;
  escena.add(cuerpo, borde, borde2);

  const pulsos = [];
  const geoPulso = new THREE.RingGeometry(0.96, 1.0, 6);
  function pulso(color) {
    const m = new THREE.Mesh(geoPulso, new THREE.MeshBasicMaterial({ color: color ?? colorEstado.getHex(), transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.rotation.z = Math.PI / 6; m.position.y = 0.03; m.userData.t = 0;
    escena.add(m); pulsos.push(m);
  }

  // Lluvia de códigos en profundidad.
  const N = retrato ? 700 : movil ? 900 : 2400;
  const pos = new Float32Array(N * 3), dato = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 3.4 + Math.pow(Math.random(), 0.7) * 15, a = Math.random() * Math.PI * 2;
    pos[i * 3] = Math.cos(a) * r; pos[i * 3 + 1] = Math.random() * 16 - 3; pos[i * 3 + 2] = Math.sin(a) * r - 2;
    dato[i * 3] = Math.floor(Math.random() * 64); dato[i * 3 + 1] = 0.5 + Math.random() * 1.4; dato[i * 3 + 2] = Math.random();
  }
  const geoLluvia = new THREE.BufferGeometry();
  geoLluvia.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geoLluvia.setAttribute("dato", new THREE.BufferAttribute(dato, 3));
  const matLluvia = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uT: { value: 0 }, uAtlas: { value: atlasDeGlifos() }, uColor: { value: new THREE.Vector3(...NOCHE.glifo) }, uEscala: { value: renderer.getPixelRatio() } },
    vertexShader: `
      attribute vec3 dato; uniform float uT; uniform float uEscala; varying float vG; varying float vB;
      void main() {
        vec3 p = position;
        p.y = mod(p.y - uT * dato.y + 3.0, 16.0) - 3.0;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uEscala * 150.0 / -mv.z;
        vG = mod(dato.x + floor(uT * 2.0 * dato.z + dato.z * 9.0), 64.0);
        vB = (0.25 + 0.75 * dato.z) * smoothstep(-3.0, 0.5, p.y) * smoothstep(26.0, 6.0, -mv.z);
      }`,
    fragmentShader: `
      uniform sampler2D uAtlas; uniform vec3 uColor; varying float vG; varying float vB;
      void main() {
        vec2 celda = vec2(mod(vG, 8.0), floor(vG / 8.0));
        vec2 uv = (celda + gl_PointCoord) / 8.0;
        float a = texture2D(uAtlas, vec2(uv.x, 1.0 - uv.y)).r;
        gl_FragColor = vec4(uColor, a * vB);
      }`,
  });
  const lluvia = new THREE.Points(geoLluvia, matLluvia); lluvia.frustumCulled = false;
  escena.add(lluvia);

  // Rutas y pedidos.
  const rutas = [];
  const matRuta = new THREE.MeshBasicMaterial({ color: 0x19c8ff, transparent: true, opacity: 0.28 });
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.5, r = 11 + (i % 3) * 2.2;
    const c = new THREE.CatmullRomCurve3([
      new THREE.Vector3(Math.cos(a) * r, 0.3 + (i % 2) * 2.4, Math.sin(a) * r),
      new THREE.Vector3(Math.cos(a + 0.5) * r * 0.62, 2.6 - (i % 3), Math.sin(a + 0.5) * r * 0.62),
      new THREE.Vector3(Math.cos(a + 0.2) * 4.2, 0.9 + (i % 2) * 0.8, Math.sin(a + 0.2) * 4.2),
      new THREE.Vector3(Math.cos(a) * 1.9, 0.12, Math.sin(a) * 1.9),
    ]);
    rutas.push(c);
    escena.add(new THREE.Mesh(new THREE.TubeGeometry(c, 90, 0.008, 5, false), matRuta));
  }
  const P = retrato || movil ? 18 : 36;
  const cajas = new THREE.InstancedMesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), new THREE.MeshBasicMaterial({ toneMapped: false }), P);
  const viaje = Array.from({ length: P }, (_, i) => ({ id: 48100 + Math.floor(Math.random() * 800), ruta: i % rutas.length, t: Math.random(), v: 0.035 + Math.random() * 0.03, novedad: false }));
  const tmp = new THREE.Object3D(), col = new THREE.Color();
  escena.add(cajas);

  // Lyan con esqueleto y animaciones.
  const lyan = new THREE.Group(); escena.add(lyan);
  let listo = false, mixer = null, actual = null, brillo = [];
  const acciones = {};
  function animar(nombre, { una = false, vuelve = "reposo" } = {}) {
    const a = acciones[nombre];
    if (!a || a === actual) return;
    a.reset(); a.setLoop(una ? THREE.LoopOnce : THREE.LoopRepeat, Infinity); a.clampWhenFinished = una;
    if (actual) a.crossFadeFrom(actual, 0.35, false);
    a.play(); actual = a; a.userData = { vuelve: una ? vuelve : null };
  }
  new GLTFLoader().load(modelo, (g) => {
    const m = g.scene;
    const caja = new THREE.Box3().setFromObject(m), tam = caja.getSize(new THREE.Vector3()), centro = caja.getCenter(new THREE.Vector3());
    const k = 2.35 / tam.y;
    m.scale.setScalar(k); m.position.set(-centro.x * k, -caja.min.y * k, -centro.z * k);
    m.traverse((o) => {
      if (!o.isMesh) return;
      o.frustumCulled = false;
      const mat = o.material;
      if (mat && mat.map) { mat.emissiveMap = mat.map; mat.emissive = new THREE.Color(0x19c8ff); mat.emissiveIntensity = 0.0; brillo.push(mat); }
    });
    if (g.animations.length) {
      mixer = new THREE.AnimationMixer(m);
      g.animations.forEach((clip) => { acciones[clip.name] = mixer.clipAction(clip); });
      mixer.addEventListener("finished", (e) => { const v = e.action.userData?.vuelve; if (v) animar(v); });
      animar("saludo", { una: true });
    }
    lyan.add(m); listo = true; onProgreso?.(1); onListo?.(); pulso();
  }, (e) => { if (e.total) onProgreso?.(Math.min(0.98, e.loaded / e.total)); }, (e) => onError?.(e));

  // Trabajo de Lyan: vigila → novedad → resuelto → vigila.
  let estado = "vigila", caso = null, espera = 2.5, destello = 0;
  const colorEstado = new THREE.Color(0x19c8ff), colorMeta = new THREE.Color(0x19c8ff);
  let tema = NOCHE;
  function pasar(nuevo, detalle) {
    estado = nuevo;
    colorMeta.setHex(tema === DIA ? ESTADOS[nuevo].dia : ESTADOS[nuevo].noche);
    destello = 1;
    onEstado?.(nuevo, detalle);
  }

  const puntero = new THREE.Vector2(), suave = new THREE.Vector2();
  let avance = 0, avanceSuave = 0, activo = true, raf = 0, giroCaso = 0, clics = 0;
  const alMover = (e) => { puntero.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1); };
  const alScroll = () => { const max = document.documentElement.scrollHeight - window.innerHeight; avance = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0; };
  const alClic = () => { pulso(); destello = 1; if (estado === "vigila") animar(clics++ % 2 ? "festejo" : "saludo", { una: true }); };
  const alVer = () => { activo = !document.hidden; if (activo && !raf) raf = requestAnimationFrame(cuadro); };
  function medir() { const w = ancho(), h = alto(); renderer.setSize(w, h, false); camara.aspect = w / h; camara.updateProjectionMatrix(); }
  function aplicarTema() {
    tema = document.documentElement.classList.contains("matrix-day") ? DIA : NOCHE;
    if (retrato) renderer.setClearColor(0x000000, 0); else renderer.setClearColor(tema.fondo, 1);
    escena.fog.color.setHex(tema.niebla); cuerpo.material.color.setHex(tema.suelo);
    matLluvia.blending = tema === DIA ? THREE.NormalBlending : THREE.AdditiveBlending; matLluvia.needsUpdate = true;
    ambiente.intensity = 0.8 * tema.luz; frente.intensity = 2.2 * tema.luz;
    colorMeta.setHex(tema === DIA ? ESTADOS[estado].dia : ESTADOS[estado].noche);
  }
  const observador = new MutationObserver(aplicarTema);
  observador.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  const tamano = retrato && window.ResizeObserver ? new ResizeObserver(medir) : null;
  tamano?.observe(canvas);

  const reloj = new THREE.Clock();
  const pA = new THREE.Vector3(), pB = new THREE.Vector3(), mA = new THREE.Vector3(), mB = new THREE.Vector3(), pc = new THREE.Vector3();
  function cuadro() {
    raf = 0;
    if (!activo) return;
    const dt = Math.min(reloj.getDelta(), 0.05), t = reloj.elapsedTime;
    avanceSuave += (avance - avanceSuave) * Math.min(1, dt * 3.2);
    suave.lerp(puntero, Math.min(1, dt * 4));
    mixer?.update(quieto ? 0 : dt);

    // Cámara.
    if (retrato) {
      camara.position.set(suave.x * 0.3, 1.5 - suave.y * 0.15, 5.6); mira.set(0, 1.12, 0);
    } else {
      let i = 0; while (i < CAMARA.length - 2 && avanceSuave > CAMARA[i + 1].p) i++;
      const a = CAMARA[i], b = CAMARA[i + 1];
      let k = (avanceSuave - a.p) / (b.p - a.p); k = k * k * (3 - 2 * Math.min(1, Math.max(0, k)));
      const lado = movil ? 0 : 1;
      pA.set(a.pos[0] * lado, a.pos[1], a.pos[2] * (movil ? (i === 0 ? 1.55 : 1.25) : 1)); pB.set(b.pos[0] * (movil ? 0.6 : 1), b.pos[1], b.pos[2] * (movil ? 1.25 : 1));
      mA.set(a.mira[0] * lado, a.mira[1] - (movil && i === 0 ? 1.15 : 0), a.mira[2]); mB.set(b.mira[0], b.mira[1], b.mira[2]);
      camara.position.lerpVectors(pA, pB, k); camara.position.x += suave.x * 0.25; camara.position.y -= suave.y * 0.15;
      mira.lerpVectors(mA, mB, k);
    }
    camara.lookAt(mira);

    // Pedidos por las rutas.
    for (let j = 0; j < P; j++) {
      const v = viaje[j];
      const frenado = v === caso && estado === "novedad";
      if (!quieto) v.t += v.v * dt * (frenado ? 0.12 : 1);
      if (v.t > 1) { v.t = 0; v.id = 48100 + Math.floor(Math.random() * 800); v.novedad = false; v.hecho = false; }
      rutas[v.ruta].getPointAt(v.t, tmp.position);
      if (v === caso) pc.copy(tmp.position);
      const cerca = Math.min(1, Math.max(0, (tmp.position.distanceTo(camara.position) - 1.6) / 2.4));
      const s = (0.7 + Math.sin(v.t * Math.PI) * 0.5 + (v === caso ? 0.9 : 0)) * cerca;
      tmp.scale.setScalar(Math.max(0.0001, s)); tmp.rotation.set(t * 0.6 + j, t * 0.4 + j, 0); tmp.updateMatrix();
      cajas.setMatrixAt(j, tmp.matrix);
      col.setHex(v.novedad ? CAJA[1] : v.hecho ? CAJA[2] : CAJA[0]); cajas.setColorAt(j, col);
    }
    cajas.instanceMatrix.needsUpdate = true; if (cajas.instanceColor) cajas.instanceColor.needsUpdate = true;

    // Trabajo de Lyan.
    if (listo && !quieto) {
      espera -= dt;
      if (estado === "vigila" && espera <= 0) {
        caso = viaje.find((v) => v.t > 0.5 && v.t < 0.62 && !v.hecho) || null;
        if (caso) { caso.novedad = true; espera = 3.4; pasar("novedad", caso.id); animar("alerta"); pulso(); }
        else espera = 0.4;
      } else if (estado === "novedad" && espera <= 0) {
        caso.novedad = false; caso.hecho = true; espera = 3.0; pasar("resuelto", caso.id); animar("festejo", { una: true }); pulso();
      } else if (estado === "resuelto" && espera <= 0) {
        caso = null; espera = 4 + Math.random() * 3; pasar("vigila"); animar("reposo");
      }
    }

    // Lyan mira a la cámara, o al pedido que está atendiendo.
    const haciaCamara = Math.atan2(camara.position.x - mira.x * 0.4, camara.position.z) * 0.85;
    if (caso && estado === "novedad") giroCaso = Math.atan2(pc.x, pc.z);
    // Se voltea hacia el pedido, pero nunca le da la espalda a quien mira (máximo ~55° desde la cámara).
    const desvio = Math.atan2(Math.sin(giroCaso - haciaCamara), Math.cos(giroCaso - haciaCamara));
    const meta = caso && estado === "novedad" ? haciaCamara + Math.max(-0.95, Math.min(0.95, desvio)) : haciaCamara + suave.x * 0.5;
    lyan.rotation.y += (meta - lyan.rotation.y) * Math.min(1, dt * 4);
    lyan.rotation.x += ((suave.y * 0.1) - lyan.rotation.x) * Math.min(1, dt * 5);
    if (!mixer) lyan.position.y = quieto ? 0 : Math.sin(t * 1.6) * 0.035;

    // Color del estado: plataforma, rutas, luz y los circuitos de Lyan.
    colorEstado.lerp(colorMeta, Math.min(1, dt * 3));
    destello = Math.max(0, destello - dt * 1.4);
    matLinea.color.copy(colorEstado); matLinea2.color.copy(colorEstado); matRuta.color.copy(colorEstado); base.color.copy(colorEstado);
    base.intensity = 14 + Math.sin(t * 2.2) * 3 + destello * 34;
    matLluvia.uniforms.uColor.value.set(colorEstado.r * (tema === DIA ? 0.6 : 1), colorEstado.g * (tema === DIA ? 0.6 : 1), colorEstado.b * (tema === DIA ? 0.6 : 1));
    const fuerza = (estado === "resuelto" ? 0.14 : estado === "novedad" ? 0.06 : 0.0) + destello * 0.18;       // tiñe los circuitos sin lavar el pelaje
    for (const m of brillo) { m.emissive.copy(colorEstado); m.emissiveIntensity += (fuerza - m.emissiveIntensity) * Math.min(1, dt * 4); }

    if (!quieto) { matLluvia.uniforms.uT.value = t; borde2.rotation.z += dt * (estado === "novedad" ? 0.5 : 0.08); }

    for (let j = pulsos.length - 1; j >= 0; j--) {
      const m = pulsos[j]; m.userData.t += dt;
      const e = m.userData.t / 1.4; m.scale.setScalar(1.8 + e * 9); m.material.opacity = Math.max(0, 0.9 * (1 - e));
      if (e >= 1) { escena.remove(m); m.material.dispose(); pulsos.splice(j, 1); }
    }

    renderer.render(escena, camara);
    if (!quieto || !listo || pulsos.length || Math.abs(avance - avanceSuave) > 0.001) raf = requestAnimationFrame(cuadro);
  }

  medir(); aplicarTema(); alScroll();
  const alRodar = () => { alScroll(); if (activo && !raf) raf = requestAnimationFrame(cuadro); };
  window.addEventListener("resize", medir);
  window.addEventListener("pointermove", alMover, { passive: true });
  if (!retrato) window.addEventListener("scroll", alRodar, { passive: true });
  (retrato ? canvas : window).addEventListener("pointerdown", alClic, { passive: true });
  document.addEventListener("visibilitychange", alVer);
  raf = requestAnimationFrame(cuadro);

  return {
    pulso,
    destruir() {
      activo = false; cancelAnimationFrame(raf); observador.disconnect(); tamano?.disconnect();
      window.removeEventListener("resize", medir); window.removeEventListener("pointermove", alMover); window.removeEventListener("scroll", alRodar);
      (retrato ? canvas : window).removeEventListener("pointerdown", alClic); document.removeEventListener("visibilitychange", alVer);
      escena.traverse((o) => { o.geometry?.dispose?.(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.map?.dispose?.(); m.dispose?.(); }); });
      renderer.dispose();
    },
  };
}
