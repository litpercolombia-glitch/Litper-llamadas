import { semaforoStyles } from "../lib/api";

export default function Semaforo({ value = "gris", showLabel = true, testId }) {
  const s = semaforoStyles[value] || semaforoStyles.gris;
  return (
    <span
      data-testid={testId || `semaforo-${value}`}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 border rounded-sm text-[11px] font-mono uppercase tracking-wider ${s.cls}`}
    >
      <span className="semaforo-dot" style={{ background: s.dot }} />
      {showLabel && s.label}
    </span>
  );
}
