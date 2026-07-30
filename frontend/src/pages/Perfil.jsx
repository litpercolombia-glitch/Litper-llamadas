import { useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import HowItWorks from "../components/HowItWorks";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  User, Camera, LockKey, Buildings, Trash, GoogleLogo,
  FloppyDisk, ShieldCheck,
} from "@phosphor-icons/react";

/**
 * Perfil de cuenta — pattern from Vercel / Linear / Stripe. All writes go
 * through /api/auth/* endpoints so no secrets are ever echoed to the client.
 */
export default function PerfilPage() {
  const [me, setMe]     = useState(null);
  const [org, setOrg]   = useState(null);
  const [nombre, setNombre]     = useState("");
  const [email, setEmail]       = useState("");
  const [orgName, setOrgName]   = useState("");
  const [pwdCurrent, setPwdCurrent] = useState("");
  const [pwdNew, setPwdNew]         = useState("");
  const [pwdNew2, setPwdNew2]       = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPwd, setSavingPwd] = useState(false);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const fileRef = useRef(null);

  const isGoogle = me?.provider === "google";

  const load = async () => {
    try {
      const [meR, orgR] = await Promise.all([
        api.get("/auth/me"), api.get("/auth/org"),
      ]);
      const u = meR.data?.user; const o = orgR.data?.org;
      setMe(u); setOrg(o);
      setNombre(u?.nombre || "");
      setEmail(u?.email || "");
      setOrgName(o?.name || "");
    } catch {
      toast.error("No pudimos cargar tu perfil.");
    }
  };
  useEffect(() => { load(); }, []);

  const saveProfile = async (e) => {
    e?.preventDefault?.();
    setSavingProfile(true);
    try {
      const payload = {};
      if (nombre.trim() && nombre.trim() !== me?.nombre) payload.nombre = nombre.trim();
      if (email.trim().toLowerCase() !== (me?.email || "").toLowerCase()) payload.email = email.trim();
      if (orgName.trim() && orgName.trim() !== org?.name) payload.org_name = orgName.trim();
      if (Object.keys(payload).length === 0) { toast.info("Nada que guardar."); return; }
      const r = await api.put("/auth/profile", payload);
      setMe(r.data?.user); setOrg(r.data?.org);
      toast.success("Guardado.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo guardar.");
    } finally { setSavingProfile(false); }
  };

  const savePassword = async (e) => {
    e?.preventDefault?.();
    if (pwdNew.length < 6) { toast.error("Mínimo 6 caracteres."); return; }
    if (pwdNew !== pwdNew2) { toast.error("Las contraseñas no coinciden."); return; }
    setSavingPwd(true);
    try {
      await api.put("/auth/password", {
        current_password: pwdCurrent, new_password: pwdNew,
      });
      toast.success("Contraseña actualizada.");
      setPwdCurrent(""); setPwdNew(""); setPwdNew2("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo cambiar la contraseña.");
    } finally { setSavingPwd(false); }
  };

  const onPickFile = () => fileRef.current?.click();

  const onFile = (evt) => {
    const f = evt.target.files?.[0];
    if (!f) return;
    if (!/^image\/(png|jpe?g|webp)$/i.test(f.type)) {
      toast.error("Solo PNG, JPG o WebP.");
      evt.target.value = "";
      return;
    }
    if (f.size > 2 * 1024 * 1024) {
      toast.error("La imagen supera 2 MB.");
      evt.target.value = "";
      return;
    }
    // Client-side square crop via canvas.
    const url = URL.createObjectURL(f);
    const img = new Image();
    img.onload = async () => {
      const side = Math.min(img.width, img.height);
      const cx = (img.width - side) / 2;
      const cy = (img.height - side) / 2;
      const canvas = document.createElement("canvas");
      canvas.width = 512; canvas.height = 512;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, cx, cy, side, side, 0, 0, 512, 512);
      URL.revokeObjectURL(url);
      const dataUrl = canvas.toDataURL(f.type === "image/png" ? "image/png" : "image/webp", 0.85);
      setSavingAvatar(true);
      try {
        await api.post("/auth/avatar", { data_url: dataUrl });
        setMe((m) => ({ ...m, picture: dataUrl }));
        toast.success("Foto actualizada.");
      } catch (err) {
        toast.error(err?.response?.data?.detail || "No se pudo subir.");
      } finally { setSavingAvatar(false); evt.target.value = ""; }
    };
    img.src = url;
  };

  const removeAvatar = async () => {
    setSavingAvatar(true);
    try {
      await api.delete("/auth/avatar");
      setMe((m) => ({ ...m, picture: null }));
      toast.success("Foto eliminada.");
    } catch { toast.error("No se pudo eliminar."); }
    finally { setSavingAvatar(false); }
  };

  return (
    <Layout title="Perfil" subtitle="Ajustes de tu cuenta.">
      <HowItWorks
        testIdPrefix="perfil-howitworks"
        intro="Aquí gestionas tu foto, nombre, correo, contraseña y los datos de tu organización."
        steps={[
          "Sube tu foto (arrastrada a cuadrado, máximo 2 MB).",
          "Cambia tu nombre visible; el email requiere que confirmes la contraseña actual.",
          "Si iniciaste con Google, la contraseña la gestiona Google (no aparece el campo).",
          "Guarda cambios — Zynex avisa con un toast en la esquina.",
        ]}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl">
        {/* Avatar */}
        <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5"
             data-testid="perfil-avatar-card">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">Foto de perfil</div>
          <div className="flex flex-col items-center gap-3">
            <div className="w-28 h-28 rounded-full overflow-hidden border border-zinc-700 bg-zinc-800 grid place-items-center">
              {me?.picture ? (
                <img src={me.picture} alt="avatar" className="w-full h-full object-cover"
                     data-testid="perfil-avatar-img" />
              ) : (
                <User size={44} className="text-zinc-500" />
              )}
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              <Button size="sm" onClick={onPickFile} disabled={savingAvatar}
                      data-testid="perfil-avatar-upload"
                      className="btn-cta-grad rounded-sm">
                <Camera size={13} className="mr-1" />
                {savingAvatar ? "Subiendo…" : "Subir foto"}
              </Button>
              {me?.picture && (
                <Button size="sm" variant="outline" onClick={removeAvatar} disabled={savingAvatar}
                        data-testid="perfil-avatar-remove"
                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                  <Trash size={13} className="mr-1" /> Quitar
                </Button>
              )}
            </div>
            <p className="text-[11px] text-zinc-500 text-center leading-snug">
              PNG, JPG o WebP. Máx. 2 MB. Se recorta cuadrada.
            </p>
            <input ref={fileRef} type="file"
                   accept="image/png,image/jpeg,image/webp"
                   onChange={onFile} className="hidden"
                   data-testid="perfil-avatar-input" />
          </div>
        </div>

        {/* Profile fields */}
        <form onSubmit={saveProfile}
              className="md:col-span-2 border border-zinc-800 rounded-sm bg-zinc-900/40 p-5 space-y-4"
              data-testid="perfil-form">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 flex items-center gap-2">
            <User size={12} /> Cuenta
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Nombre para mostrar</label>
            <Input value={nombre} onChange={(e) => setNombre(e.target.value)}
                   data-testid="perfil-nombre"
                   className="bg-black/40 border-zinc-700 text-white" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1 flex items-center gap-2">
              Email
              {isGoogle && (
                <span className="inline-flex items-center gap-1 text-[10px] text-white/70 bg-zinc-800 border border-zinc-700 rounded-sm px-1.5 py-0.5">
                  <GoogleLogo size={10} weight="bold" /> conectado con Google
                </span>
              )}
            </label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                   disabled={isGoogle}
                   data-testid="perfil-email"
                   className="bg-black/40 border-zinc-700 text-white disabled:opacity-60" />
          </div>

          <div className="pt-4 border-t border-zinc-800 space-y-2">
            <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 flex items-center gap-2">
              <Buildings size={12} /> Organización
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Nombre de la empresa</label>
              <Input value={orgName} onChange={(e) => setOrgName(e.target.value)}
                     data-testid="perfil-org-name"
                     className="bg-black/40 border-zinc-700 text-white" />
            </div>
            <div className="text-[10px] font-mono text-zinc-500">
              org_id: <span className="text-zinc-300" data-testid="perfil-org-id">{org?.id || "—"}</span>
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={savingProfile}
                    data-testid="perfil-save"
                    className="btn-cta-grad rounded-sm">
              <FloppyDisk size={13} className="mr-1" />
              {savingProfile ? "Guardando…" : "Guardar cambios"}
            </Button>
          </div>
        </form>
      </div>

      {/* Password */}
      <div className="mt-6 border border-zinc-800 rounded-sm bg-zinc-900/40 p-5 max-w-3xl"
           data-testid="perfil-password-card">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3 flex items-center gap-2">
          <LockKey size={12} /> Contraseña
        </div>
        {isGoogle ? (
          <div className="text-sm text-zinc-300 flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-400" weight="fill" />
            Gestionado por Google — cambia tu contraseña en{" "}
            <a href="https://myaccount.google.com/security" target="_blank" rel="noreferrer"
               className="text-cyan-300 hover:underline">Google Cuenta</a>.
          </div>
        ) : (
          <form onSubmit={savePassword} className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input type="password" placeholder="Contraseña actual" value={pwdCurrent}
                   onChange={(e) => setPwdCurrent(e.target.value)}
                   data-testid="perfil-pwd-current" required minLength={1}
                   className="bg-black/40 border-zinc-700 text-white" />
            <Input type="password" placeholder="Nueva (mín. 6)" value={pwdNew}
                   onChange={(e) => setPwdNew(e.target.value)}
                   data-testid="perfil-pwd-new" required minLength={6}
                   className="bg-black/40 border-zinc-700 text-white" />
            <Input type="password" placeholder="Confirmar nueva" value={pwdNew2}
                   onChange={(e) => setPwdNew2(e.target.value)}
                   data-testid="perfil-pwd-new2" required minLength={6}
                   className="bg-black/40 border-zinc-700 text-white" />
            <div className="md:col-span-3 flex justify-end">
              <Button type="submit" disabled={savingPwd}
                      data-testid="perfil-pwd-save"
                      className="btn-cta-grad rounded-sm">
                {savingPwd ? "Cambiando…" : "Cambiar contraseña"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </Layout>
  );
}
