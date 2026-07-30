import { useState } from "react";
import { Question, CaretDown, Sparkle } from "@phosphor-icons/react";

/**
 * Reusable "¿Cómo funciona?" accordion — sits at the top of every hub page.
 * The trigger has a subtle cyan→violet pulsing gradient (respects
 * prefers-reduced-motion, honouring accessibility).
 */
export default function HowItWorks({
  title = "¿Cómo funciona?",
  intro,
  steps = [],
  links = [],
  testIdPrefix = "howitworks",
  defaultOpen = false,
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-6" data-testid={`${testIdPrefix}-wrap`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        data-testid={`${testIdPrefix}-toggle`}
        className="how-it-works-btn relative inline-flex items-center gap-2 px-4 py-2.5 rounded-sm text-sm font-medium text-white border border-white/10 overflow-hidden"
        aria-expanded={open}
      >
        <span className="hiw-glow" aria-hidden="true" />
        <Question size={16} weight="fill" className="relative z-10" />
        <span className="relative z-10">{title}</span>
        <CaretDown
          size={13}
          weight="bold"
          className={`relative z-10 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className="mt-3 border border-zinc-800 rounded-sm bg-zinc-900/50 p-5 space-y-3"
          data-testid={`${testIdPrefix}-panel`}
        >
          {intro && (
            <p className="text-sm text-zinc-200 leading-relaxed">{intro}</p>
          )}
          {steps.length > 0 && (
            <ol className="text-sm text-zinc-300 space-y-1.5 list-decimal pl-5">
              {steps.map((s, i) => (
                <li key={i} data-testid={`${testIdPrefix}-step-${i}`}>{s}</li>
              ))}
            </ol>
          )}
          {links.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {links.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  target={l.external ? "_blank" : undefined}
                  rel={l.external ? "noreferrer" : undefined}
                  className="text-xs text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1"
                >
                  <Sparkle size={11} weight="fill" />
                  {l.label}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
