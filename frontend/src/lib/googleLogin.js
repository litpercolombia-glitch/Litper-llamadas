/**
 * Acceso con Google (opcional, apagado por defecto).
 *
 * Depende de un servicio externo de autenticación, así que solo se muestra
 * si el despliegue lo activa de forma explícita con DOS variables:
 *   REACT_APP_GOOGLE_LOGIN=1
 *   REACT_APP_GOOGLE_AUTH_URL=https://<servicio-de-acceso>/
 * Sin ellas, la app ofrece únicamente correo y contraseña.
 */
const AUTH_URL = (process.env.REACT_APP_GOOGLE_AUTH_URL || "").trim();

export const GOOGLE_LOGIN_ENABLED =
  process.env.REACT_APP_GOOGLE_LOGIN === "1" && /^https:\/\//i.test(AUTH_URL);

export function startGoogleLogin() {
  if (!GOOGLE_LOGIN_ENABLED) return;
  const redirectUrl = window.location.origin + "/app";
  const sep = AUTH_URL.includes("?") ? "&" : "?";
  window.location.href = `${AUTH_URL}${sep}redirect=${encodeURIComponent(redirectUrl)}`;
}
