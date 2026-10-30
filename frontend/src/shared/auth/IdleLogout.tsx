import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth, useUser } from "@/shared/auth/AuthProvider";
import { notify } from "@/shared/lib/notify";
import { Button, Modal } from "@/shared/ui";

/** Última actividad compartida entre pestañas: usar el sistema en una mantiene abiertas las demás. */
export const LAST_ACTIVITY_KEY = "topico.lastActivity";
const WARNING_MS = 60_000;
const WRITE_EVERY_MS = 5_000;
const EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;

function readShared(): number {
  try {
    return Number(localStorage.getItem(LAST_ACTIVITY_KEY)) || 0;
  } catch {
    return 0;
  }
}

function writeShared(value: number): void {
  try {
    localStorage.setItem(LAST_ACTIVITY_KEY, String(value));
  } catch {
    // Sin almacenamiento (navegación privada): cuenta solo esta pestaña.
  }
}

/**
 * Cierra la sesión tras `idle_timeout_minutes` sin uso (parámetro auth.idle_timeout_minutes; 0 = desactivado).
 * Un minuto antes avisa con una cuenta regresiva; durante el aviso solo «Seguir conectado» mantiene la sesión.
 */
export function IdleLogout() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const timeoutMs = user.idle_timeout_minutes * 60_000;
  const last = useRef(0); // se fija al montar (en el efecto)
  const warningRef = useRef(false);
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (timeoutMs <= 0) return;
    last.current = Date.now();
    writeShared(last.current);
    let lastWrite = last.current;

    const onActivity = () => {
      if (warningRef.current) return; // con el aviso abierto hay que confirmar explícitamente
      const now = Date.now();
      last.current = now;
      if (now - lastWrite >= WRITE_EVERY_MS) {
        lastWrite = now;
        writeShared(now);
      }
    };
    for (const event of EVENTS) window.addEventListener(event, onActivity, { passive: true });

    const timer = window.setInterval(() => {
      const latest = Math.max(last.current, readShared());
      last.current = latest;
      const left = latest + timeoutMs - Date.now();
      if (left <= 0) {
        window.clearInterval(timer);
        warningRef.current = false;
        setRemaining(null);
        void logout().finally(() => {
          notify.warning("Sesión cerrada por inactividad", "Por seguridad, ingrese nuevamente con su DNI y contraseña.");
          navigate("/login", { replace: true });
        });
        return;
      }
      warningRef.current = left <= WARNING_MS;
      setRemaining(warningRef.current ? left : null);
    }, 1_000);

    return () => {
      window.clearInterval(timer);
      for (const event of EVENTS) window.removeEventListener(event, onActivity);
    };
  }, [timeoutMs, logout, navigate]);

  const stay = () => {
    last.current = Date.now();
    writeShared(last.current);
    warningRef.current = false;
    setRemaining(null);
  };

  const seconds = remaining === null ? 0 : Math.ceil(remaining / 1000);
  return (
    <Modal
      open={remaining !== null}
      onOpenChange={(open) => !open && stay()}
      title="¿Sigue ahí?"
      description="Por seguridad, la sesión se cierra cuando el sistema no se usa."
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={() => void logout().then(() => navigate("/login", { replace: true }))}>
            Cerrar sesión
          </Button>
          <Button onClick={stay} autoFocus>
            Seguir conectado
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink-muted" aria-live="polite">
        Su sesión se cerrará en <span className="tabular font-semibold text-ink">{seconds} s</span> por inactividad.
      </p>
    </Modal>
  );
}
