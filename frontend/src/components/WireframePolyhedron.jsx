import { useMemo } from "react";

/**
 * WireframePolyhedron — SVG icosahedron rendered as neon wireframe.
 * The outer container rotates via CSS (see .wireframe-3d), while each
 * edge picks a stroke color along the cyan→magenta gradient so the whole
 * shape "destella" naturally.
 */
export default function WireframePolyhedron({ size = 380 }) {
  // 12 vertices of an icosahedron (golden ratio)
  const { verts, edges } = useMemo(() => {
    const t = (1 + Math.sqrt(5)) / 2;
    const raw = [
      [-1,  t,  0], [ 1,  t,  0], [-1, -t,  0], [ 1, -t,  0],
      [ 0, -1,  t], [ 0,  1,  t], [ 0, -1, -t], [ 0,  1, -t],
      [ t,  0, -1], [ t,  0,  1], [-t,  0, -1], [-t,  0,  1],
    ];
    // Normalize to unit sphere and scale
    const R = 90;
    const verts = raw.map(([x, y, z]) => {
      const l = Math.hypot(x, y, z);
      return [(x / l) * R, (y / l) * R, (z / l) * R];
    });

    // 30 edges (icosahedron)
    const edges = [
      [0,1],[0,5],[0,7],[0,10],[0,11],
      [1,5],[1,7],[1,8],[1,9],
      [2,3],[2,4],[2,6],[2,10],[2,11],
      [3,4],[3,6],[3,8],[3,9],
      [4,5],[4,9],[4,11],
      [5,9],[5,11],
      [6,7],[6,8],[6,10],
      [7,8],[7,10],
      [8,9],
      [10,11],
    ];
    return { verts, edges };
  }, []);

  // Simple isometric-ish projection (rotation happens on the parent container
  // via CSS so we just project X,Y here with a slight Y tilt).
  const project = ([x, y, z]) => {
    const cx = size / 2;
    const cy = size / 2;
    // subtle static tilt for depth
    const cosT = Math.cos(0.35);
    const sinT = Math.sin(0.35);
    const yy = y * cosT - z * sinT;
    return [cx + x, cy + yy];
  };

  const grad = "url(#zx-grad)";

  return (
    <div className="wireframe-3d" style={{ width: size, height: size }}
         data-testid="hero-wireframe">
      <div className="wireframe-vignette" />
      <svg viewBox={`0 0 ${size} ${size}`} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="zx-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%"   stopColor="#00D8FF" />
            <stop offset="35%"  stopColor="#0A84FF" />
            <stop offset="70%"  stopColor="#7C5CFF" />
            <stop offset="100%" stopColor="#C04BFF" />
          </linearGradient>
          <radialGradient id="zx-node" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#ffffff" stopOpacity="1" />
            <stop offset="45%" stopColor="#5AC8FA" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#7C5CFF" stopOpacity="0" />
          </radialGradient>
          <filter id="zx-blur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
        </defs>

        {/* Glow underlay */}
        <g opacity="0.55" filter="url(#zx-blur)">
          {edges.map(([a, b], i) => {
            const [x1, y1] = project(verts[a]);
            const [x2, y2] = project(verts[b]);
            return <line key={`b-${i}`} x1={x1} y1={y1} x2={x2} y2={y2}
                         stroke={grad} strokeWidth="3" strokeLinecap="round" />;
          })}
        </g>

        {/* Crisp edges */}
        <g>
          {edges.map(([a, b], i) => {
            const [x1, y1] = project(verts[a]);
            const [x2, y2] = project(verts[b]);
            return <line key={`e-${i}`} x1={x1} y1={y1} x2={x2} y2={y2}
                         stroke={grad} strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.95" />;
          })}
        </g>

        {/* Vertex nodes */}
        <g>
          {verts.map(([, , _z], i) => {
            const [x, y] = project(verts[i]);
            return (
              <g key={`v-${i}`}>
                <circle cx={x} cy={y} r="10" fill="url(#zx-node)" opacity="0.55" />
                <circle cx={x} cy={y} r="2.4" fill="#ffffff" />
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
