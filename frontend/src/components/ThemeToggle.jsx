import { useEffect, useState } from "react";
import { Sun, Moon } from "@phosphor-icons/react";

const KEY = "litper-theme";

export function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem(KEY) || "night");

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("matrix-day", "matrix-night");
    root.classList.add(theme === "day" ? "matrix-day" : "matrix-night");
    localStorage.setItem(KEY, theme);
  }, [theme]);

  return [theme, setTheme];
}

export default function ThemeToggle({ testId = "theme-toggle" }) {
  const [theme, setTheme] = useTheme();
  const isDay = theme === "day";
  return (
    <button
      data-testid={testId}
      onClick={() => setTheme(isDay ? "night" : "day")}
      className="metal-surface flex items-center gap-2 px-3 h-9 text-xs font-mono uppercase tracking-widest transition hover:scale-[1.02] active:scale-[0.98]"
      title={isDay ? "Cambiar a Night Silver" : "Cambiar a Day Silver"}
    >
      {isDay
        ? <><Moon size={14} weight="duotone" /> Night</>
        : <><Sun  size={14} weight="duotone" /> Day</>}
    </button>
  );
}
