// Escena 3D de la página de inicio: Lyan en su torre de control.
// Lluvia de códigos en profundidad, rutas por donde viajan los pedidos y la mascota que responde al cursor y al clic.
// Sin datos de nadie: todo lo que se mueve es decoración.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const NOCHE = { fondo: 0x04070c, niebla: 0x04070c, linea: 0x19c8ff, glifo: [0.10, 0.78, 1.0], suelo: 0x070b12, luz: 1.0 };
const DIA = { fondo: 0xe9f1f8, niebla: 0xe9f1f8, linea: 0x0369a1, glifo: [0.02, 0.36, 0.55], suelo: 0xdbe6f0, luz: 1.9 };
const ESTADOS = [0x19c8ff, 0xffb020, 0x34e3a0];        // en camino · novedad · resuelto

// Recorrido de la cámara según el avance de la página (0 a 1).
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

export function montar(canvas, { modelo = "/lyan3d.glb", onProgreso, onListo, onError } = {}) {
  const quieto = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const movil = window.innerWidth < 720;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: !movil, powerPreference: "high-performance" }); }
  catch (e) { onError?.(e); return null; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, movil ? 1.5 : 1.75));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const escena = new THREE.Scene();
  escena.fog = new THREE.Fog(NOCHE.niebla, 9, 30);
  const camara = new THREE.PerspectiveCamera(movil ? 52 : 40, 1, 0.1, 80);
  const mira = new THREE.Vector3();

  // Luces: una fría de frente, un contraluz violeta y un resplandor desde la plataforma.
  const ambiente = new THREE.HemisphereLight(0x9fd8ff, 0x05070b, 0.8);
  const frente = new THREE.DirectionalLight(0xdff4ff, 2.2); frente.position.set(-3, 5, 6);
  const contra = new THREE.PointLight(0x7c5cff, 26, 16); contra.position.set(3.2, 3.2, -3.5);
  const base = new THREE.PointLight(0x19c8ff, 14, 9); base.position.set(0, 0.25, 1.2);
  escena.add(ambiente, frente, contra, base);

  // Plataforma hexagonal y anillos de pulso.
  const plataforma = new THREE.Group();
  const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(1.75, 1.95, 0.22, 6),
    new THREE.MeshStandardMaterial({ color: NOCHE.suelo, metalness: 0.7, roughness: 0.35 }));
  cuerpo.position.y = -0.11;
  const matLinea = new THREE.MeshBasicMaterial({ color: NOCHE.linea, transparent: true, opacity: 0.95 });
  const borde = new THREE.Mesh(new THREE.TorusGeometry(1.78, 0.022, 8, 6), matLinea);
  borde.rotation.x = Math.PI / 2; borde.rotation.z = Math.PI / 6; borde.position.y = 0.012;
  const borde2 = new THREE.Mesh(new THREE.TorusGeometry(2.6, 0.008, 6, 6), new THREE.MeshBasicMaterial({ color: NOCHE.linea, transparent: true, opacity: 0.35 }));
  borde2.rotation.copy(borde.rotation); borde2.position.y = -0.2;
  plataforma.add(cuerpo, borde, borde2);
  escena.add(plataforma);

  const pulsos = [];
  const geoPulso = new THREE.RingGeometry(0.96, 1.0, 6);
  function pulso(color = NOCHE.linea) {
    const m = new THREE.Mesh(geoPulso, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.rotation.z = Math.PI / 6; m.position.y = 0.03; m.userData.t = 0;
    escena.add(m); pulsos.push(m);
    salto = 1;
  }

  // Lluvia de códigos en profundidad.
  const N = movil ? 900 : 2400;
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
    uniforms: { uT: { value: 0 }, uAtlas: { value: atlasDeGlifos() }, uColor: { value: new THREE.Vector3(...NOCHE.glifo) }, uEscala: { value: renderer.getPixelRatio() }, uFuerza: { value: 1 } },
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
      uniform sampler2D uAtlas; uniform vec3 uColor; uniform float uFuerza; varying float vG; varying float vB;
      void main() {
        vec2 celda = vec2(mod(vG, 8.0), floor(vG / 8.0));
        vec2 uv = (celda + vec2(gl_PointCoord.x, gl_PointCoord.y)) / 8.0;
        float a = texture2D(uAtlas, vec2(uv.x, 1.0 - uv.y)).r;
        gl_FragColor = vec4(uColor, a * vB * uFuerza);
      }`,
  });
  const lluvia = new THREE.Points(geoLluvia, matLluvia); lluvia.frustumCulled = false;
  escena.add(lluvia);

  // Rutas: curvas que llegan a la plataforma, con pedidos que viajan por ellas.
  const rutas = [], tubos = [];
  const matRuta = new THREE.MeshBasicMaterial({ color: NOCHE.linea, transparent: true, opacity: 0.28 });
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.5, r = 11 + (i % 3) * 2.2;
    const c = new THREE.CatmullRomCurve3([
      new THREE.Vector3(Math.cos(a) * r, 0.3 + (i % 2) * 2.4, Math.sin(a) * r),
      new THREE.Vector3(Math.cos(a + 0.5) * r * 0.62, 2.6 - (i % 3), Math.sin(a + 0.5) * r * 0.62),
      new THREE.Vector3(Math.cos(a + 0.2) * 4.2, 0.9 + (i % 2) * 0.8, Math.sin(a + 0.2) * 4.2),
      new THREE.Vector3(Math.cos(a) * 1.9, 0.12, Math.sin(a) * 1.9),
    ]);
    rutas.push(c);
    const tubo = new THREE.Mesh(new THREE.TubeGeometry(c, 90, 0.008, 5, false), matRuta);
    tubos.push(tubo); escena.add(tubo);
  }
  const P = movil ? 18 : 36;
  const cajas = new THREE.InstancedMesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), new THREE.MeshBasicMaterial({ toneMapped: false }), P);
  const viaje = Array.from({ length: P }, (_, i) => ({ ruta: i % rutas.length, t: Math.random(), v: 0.035 + Math.random() * 0.03, novedad: i % 4 === 0 }));
  const tmp = new THREE.Object3D(), col = new THREE.Color();
  escena.add(cajas);

  // Lyan.
  const lyan = new THREE.Group(); escena.add(lyan);
  let listo = false, salto = 0;
  new GLTFLoader().load(modelo, (g) => {
    const m = g.scene;
    const caja = new THREE.Box3().setFromObject(m), tam = caja.getSize(new THREE.Vector3()), centro = caja.getCenter(new THREE.Vector3());
    const k = 2.35 / tam.y;
    m.scale.setScalar(k); m.position.set(-centro.x * k, -caja.min.y * k, -centro.z * k);
    m.traverse((o) => { if (o.isMesh && o.material) { o.material.envMapIntensity = 0.6; if ("roughness" in o.material) o.material.roughness = Math.min(1, o.material.roughness + 0.1); } });
    lyan.add(m); listo = true; onProgreso?.(1); onListo?.();
    pulso();
  }, (e) => { if (e.total) onProgreso?.(Math.min(0.98, e.loaded / e.total)); }, (e) => onError?.(e));

  // Estado.
  const puntero = new THREE.Vector2(), suave = new THREE.Vector2();
  let avance = 0, avanceSuave = 0, tema = NOCHE, activo = true, raf = 0;
  const alMover = (e) => { puntero.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1); };
  const alScroll = () => { const max = document.documentElement.scrollHeight - window.innerHeight; avance = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0; };
  const alClic = () => pulso(tema.linea);
  const alVer = () => { activo = !document.hidden; if (activo && !raf) raf = requestAnimationFrame(cuadro); };
  function medir() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false); camara.aspect = w / h; camara.updateProjectionMatrix();
  }
  function aplicarTema() {
    tema = document.documentElement.classList.contains("matrix-day") ? DIA : NOCHE;
    renderer.setClearColor(tema.fondo, 1); escena.fog.color.setHex(tema.niebla);
    matLinea.color.setHex(tema.linea); matRuta.color.setHex(tema.linea); borde2.material.color.setHex(tema.linea);
    cuerpo.material.color.setHex(tema.suelo);
    matLluvia.uniforms.uColor.value.set(...tema.glifo);
    matLluvia.blending = tema === DIA ? THREE.NormalBlending : THREE.AdditiveBlending; matLluvia.needsUpdate = true;
    ambiente.intensity = 0.8 * tema.luz; frente.intensity = 2.2 * tema.luz;
  }
  const observador = new MutationObserver(aplicarTema);
  observador.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

  const reloj = new THREE.Clock();
  const pA = new THREE.Vector3(), pB = new THREE.Vector3(), mA = new THREE.Vector3(), mB = new THREE.Vector3();
  function cuadro() {
    raf = 0;
    if (!activo) return;
    const dt = Math.min(reloj.getDelta(), 0.05), t = reloj.elapsedTime;
    avanceSuave += (avance - avanceSuave) * Math.min(1, dt * 3.2);
    suave.lerp(puntero, Math.min(1, dt * 4));

    // Cámara entre puntos clave.
    let i = 0; while (i < CAMARA.length - 2 && avanceSuave > CAMARA[i + 1].p) i++;
    const a = CAMARA[i], b = CAMARA[i + 1];
    let k = (avanceSuave - a.p) / (b.p - a.p); k = k * k * (3 - 2 * Math.min(1, Math.max(0, k)));
    const lado = movil ? 0 : 1;
    pA.set(a.pos[0] * lado, a.pos[1], a.pos[2] * (movil ? (i === 0 ? 1.55 : 1.25) : 1)); pB.set(b.pos[0] * (movil ? 0.6 : 1), b.pos[1], b.pos[2] * (movil ? 1.25 : 1));
    mA.set(a.mira[0] * lado, a.mira[1] - (movil && i === 0 ? 1.15 : 0), a.mira[2]); mB.set(b.mira[0], b.mira[1], b.mira[2]);
    camara.position.lerpVectors(pA, pB, k); camara.position.x += suave.x * 0.25; camara.position.y -= suave.y * 0.15;
    mira.lerpVectors(mA, mB, k); camara.lookAt(mira);

    // Lyan: respira, sigue el cursor y salta con el clic.
    salto = Math.max(0, salto - dt * 2.2);
    const brinco = Math.sin((1 - salto) * Math.PI) * (salto > 0 ? 0.32 : 0);
    lyan.position.y = (quieto ? 0 : Math.sin(t * 1.6) * 0.035) + brinco;
    const haciaCamara = Math.atan2(camara.position.x - mira.x * 0.4, camara.position.z) * 0.85;      // Lyan siempre mira a quien la ve
    lyan.rotation.y += ((haciaCamara + suave.x * 0.5 + Math.sin(t * 0.5) * 0.06) - lyan.rotation.y) * Math.min(1, dt * 4);
    lyan.rotation.x += ((suave.y * 0.12) - lyan.rotation.x) * Math.min(1, dt * 5);
    const aplasta = 1 + Math.sin(t * 1.6) * (quieto ? 0 : 0.008) - (salto > 0.8 ? (salto - 0.8) * 0.5 : 0);
    lyan.scale.set(1 / Math.sqrt(aplasta), aplasta, 1 / Math.sqrt(aplasta));
    base.intensity = 14 + Math.sin(t * 2.2) * 3 + salto * 30;

    if (!quieto) { matLluvia.uniforms.uT.value = t; borde2.rotation.z += dt * 0.08; }

    // Pedidos por las rutas: los de novedad llegan en ámbar y se vuelven verdes cerca de Lyan.
    for (let j = 0; j < P; j++) {
      const v = viaje[j];
      if (!quieto) v.t += v.v * dt * (v.novedad && v.t > 0.45 && v.t < 0.6 ? 0.25 : 1);
      if (v.t > 1) { v.t = 0; v.novedad = Math.random() < 0.3; }
      rutas[v.ruta].getPointAt(v.t, tmp.position);
      const cerca = Math.min(1, Math.max(0, (tmp.position.distanceTo(camara.position) - 1.6) / 2.4));   // no tapan la cámara
      const s = (0.7 + Math.sin(v.t * Math.PI) * 0.5) * cerca;
      tmp.scale.setScalar(Math.max(0.0001, s)); tmp.rotation.set(t * 0.6 + j, t * 0.4 + j, 0); tmp.updateMatrix();
      cajas.setMatrixAt(j, tmp.matrix);
      col.setHex(v.novedad ? (v.t > 0.72 ? ESTADOS[2] : ESTADOS[1]) : ESTADOS[0]);
      cajas.setColorAt(j, col);
    }
    cajas.instanceMatrix.needsUpdate = true; if (cajas.instanceColor) cajas.instanceColor.needsUpdate = true;

    for (let j = pulsos.length - 1; j >= 0; j--) {
      const m = pulsos[j]; m.userData.t += dt;
      const e = m.userData.t / 1.4; m.scale.setScalar(1.8 + e * 9); m.material.opacity = Math.max(0, 0.9 * (1 - e));
      if (e >= 1) { escena.remove(m); m.material.dispose(); pulsos.splice(j, 1); }
    }

    renderer.render(escena, camara);
    if (!quieto || !listo || pulsos.length || salto > 0 || Math.abs(avance - avanceSuave) > 0.001) raf = requestAnimationFrame(cuadro);
  }

  medir(); aplicarTema(); alScroll();
  window.addEventListener("resize", medir);
  window.addEventListener("pointermove", alMover, { passive: true });
  const alRodar = () => { alScroll(); if (activo && !raf) raf = requestAnimationFrame(cuadro); };
  window.addEventListener("scroll", alRodar, { passive: true });
  window.addEventListener("pointerdown", alClic, { passive: true });
  document.addEventListener("visibilitychange", alVer);
  raf = requestAnimationFrame(cuadro);

  return {
    pulso,
    destruir() {
      activo = false; cancelAnimationFrame(raf); observador.disconnect();
      window.removeEventListener("resize", medir); window.removeEventListener("pointermove", alMover);
      window.removeEventListener("pointerdown", alClic); window.removeEventListener("scroll", alRodar); document.removeEventListener("visibilitychange", alVer);
      escena.traverse((o) => { o.geometry?.dispose?.(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.map?.dispose?.(); m.dispose?.(); }); });
      renderer.dispose();
    },
  };
}
