import { useNavigate } from "react-router-dom";
import { ChatCircleDots } from "@phosphor-icons/react";
import { Button } from "./ui/button";
import { copilotPromptUrl } from "../constants/help";
import { useAssistantName } from "../lib/assistant";

/**
 * Estado vacío reutilizable: explica qué es la pantalla, ofrece la acción
 * principal y un atajo para pedírselo al asistente con el texto ya escrito.
 *
 *  - action: { label, onClick } | { label, to }
 *  - prompt: texto que se precarga en el asistente (/app?prompt=...)
 */
export default function EmptyState({
  icon: Icon, title, description, action, prompt, testId = "empty-state", compact = false,
}) {
  const navigate = useNavigate();
  const asistente = useAssistantName();
  const runAction = () => {
    if (!action) return;
    if (action.onClick) action.onClick();
    else if (action.to) navigate(action.to);
  };
  return (
    <div data-testid={testId}
         className={`border border-dashed border-zinc-800 rounded-sm text-center bg-zinc-900/30 ${compact ? "p-6" : "p-10"}`}>
      {Icon && <Icon size={38} className="mx-auto mb-3 text-zinc-600" weight="duotone" />}
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-zinc-400 max-w-md mx-auto mb-5 leading-relaxed">{description}</p>
      )}
      <div className="flex flex-wrap justify-center gap-2">
        {action && (
          <Button onClick={runAction} className="btn-cta-grad rounded-sm" data-testid={`${testId}-action`}>
            {action.label}
          </Button>
        )}
        {prompt && (
          <Button variant="outline" onClick={() => navigate(copilotPromptUrl(prompt))}
                  title={prompt}
                  className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800"
                  data-testid={`${testId}-ask`}>
            <ChatCircleDots size={15} weight="duotone" className="mr-1.5" />
            Pídeselo a {asistente}
          </Button>
        )}
      </div>
      {prompt && (
        <p className="text-[11px] text-zinc-500 mt-3 max-w-md mx-auto">Ejemplo: «{prompt}»</p>
      )}
    </div>
  );
}
