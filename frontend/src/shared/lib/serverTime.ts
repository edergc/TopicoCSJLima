/**
 * Hora de referencia = hora del SERVIDOR.
 *
 * Los cronómetros (tiempo en atención, tolerancia del llamado) no pueden depender del reloj
 * del PC: si está desfasado, mostraría "tolerancia vencida" antes de tiempo. Se calcula el
 * desfase con cada respuesta que trae la hora del sistema y se aplica a todos los relojes.
 */
type Listener = () => void;

let offsetMs = 0;
const listeners = new Set<Listener>();

export function syncServerTime(serverIso: string | null | undefined, sentAt = Date.now()): void {
  if (!serverIso) return;
  const server = Date.parse(serverIso);
  if (Number.isNaN(server)) return;
  const next = server - sentAt;
  if (Math.abs(next - offsetMs) > 1000) {
    offsetMs = next;
    listeners.forEach((listener) => listener());
  }
}

export function serverNow(): number {
  return Date.now() + offsetMs;
}

export function onServerTimeChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
