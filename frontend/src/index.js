import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Un solo dominio para la app: la sesión (cookie) vive en zynexapp.com y no
// viaja desde call-zynex.vercel.app (otro sitio). Redirigimos conservando la ruta.
const CANONICAL = "call.zynexapp.com";
if (typeof window !== "undefined" && window.location.hostname === "call-zynex.vercel.app") {
  window.location.replace(`https://${CANONICAL}${window.location.pathname}${window.location.search}${window.location.hash}`);
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
