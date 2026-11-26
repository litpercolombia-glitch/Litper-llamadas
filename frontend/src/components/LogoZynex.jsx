import "./logo.css";

/** Marca Zynex: emblema hexagonal y la palabra con la X en el color del estado (azul vigila, ámbar novedad, verde resuelto).
 *  El color sale de la variable CSS --estado del contenedor; sin ella usa el azul de la marca. Un destello recorre las letras cada tanto. */
export default function LogoZynex({ chico = false, className = "" }) {
  return (
    <span className={`zx-logo ${chico ? "zx-logo-s" : ""} ${className}`} aria-label="Zynex">
      <span className="zx-hex" aria-hidden="true"><span>Z</span></span>
      <span className="zx-palabra" aria-hidden="true">ZYNE<b>X</b></span>
    </span>
  );
}
