import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * AuthCallback — intercambia en silencio el `session_id` que devuelve el
 * proveedor externo de acceso con Google (solo si REACT_APP_GOOGLE_LOGIN=1)
 * por nuestra propia cookie de sesión.
 *
 * Mounted synchronously by App.js *before* the router, so it always runs
 * before ProtectedRoute checks `/api/auth/me`.
 */
export default function AuthCallback() {
  const nav = useNavigate();
  const done = useRef(false); // guards StrictMode double-mount

  useEffect(() => {
    if (done.current) return;
    done.current = true;

    const hash = window.location.hash || "";
    const params = new URLSearchParams(hash.replace(/^#/, ""));
    const sid = params.get("session_id");

    // Clean the URL immediately so a refresh doesn't re-exchange.
    if (window.history?.replaceState) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    if (!sid) { nav("/login", { replace: true }); return; }

    (async () => {
      try {
        const r = await axios.post(
          `${BACKEND_URL}/api/auth/google/session`,
          null,
          { headers: { "X-Session-ID": sid }, withCredentials: true, timeout: 15000 }
        );
        if (r.data?.ok) {
          localStorage.setItem("zynex_session_ok", "1");
          nav("/app", { replace: true });
        } else {
          nav("/login?err=oauth", { replace: true });
        }
      } catch {
        nav("/login?err=oauth", { replace: true });
      }
    })();
  }, [nav]);

  return (
    <div className="min-h-screen grid place-items-center bg-black text-white">
      <div className="text-center">
        <div className="w-14 h-14 mx-auto mb-4 border-2 border-zinc-700 border-t-white rounded-full animate-spin" />
        <div className="text-sm font-mono text-zinc-400">Iniciando sesión…</div>
      </div>
    </div>
  );
}
