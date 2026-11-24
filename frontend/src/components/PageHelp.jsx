import { Link } from "react-router-dom";
import { ChatCircleDots } from "@phosphor-icons/react";
import HowItWorks from "./HowItWorks";
import { HELP, copilotPromptUrl } from "../constants/help";
import { useAssistantName } from "../lib/assistant";

/**
 * Instrucciones de una pantalla, leídas de constants/help.js.
 * `linkAsk={false}` muestra el ejemplo como texto (páginas públicas, sin sesión).
 */
export default function PageHelp({ helpKey, linkAsk = true, defaultOpen = false }) {
  const asistente = useAssistantName(linkAsk);
  const h = HELP[helpKey];
  if (!h) return null;
  return (
    <HowItWorks
      key={helpKey}
      title={`¿Cómo funciona? · ${h.titulo}`}
      intro={h.intro}
      steps={h.pasos}
      testIdPrefix={`help-${helpKey}`}
      defaultOpen={defaultOpen}
    >
      {h.pideselo && (
        <div className="pt-3 border-t border-zinc-800" data-testid={`help-${helpKey}-ask`}>
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1.5">
            O pídeselo a {asistente}
          </div>
          {linkAsk ? (
            <Link to={copilotPromptUrl(h.pideselo)}
                  className="inline-flex items-start gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ChatCircleDots size={16} weight="duotone" className="mt-0.5 shrink-0" />
              <span>«{h.pideselo}»</span>
            </Link>
          ) : (
            <p className="text-sm text-zinc-300">«{h.pideselo}»</p>
          )}
        </div>
      )}
    </HowItWorks>
  );
}
