/**
 * Pestañas abiertas antes de publicar una versión nueva: conservan en memoria la versión anterior y,
 * al entrar a una sección, piden archivos (con hash en el nombre) que quizá ya no existen.
 * En ese caso se recarga la página una sola vez para tomar la versión nueva, en lugar de mostrar un error.
 */
const RELOAD_KEY = "topico.staleReloadAt";
const LOOP_GUARD_MS = 30_000;

export function isStaleChunkError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /dynamically imported module|module script failed|Importing a module script|Loading chunk|Unable to preload CSS/i.test(message);
}

/** Recarga una vez; devuelve false si ya se recargó hace poco (evita un ciclo si el problema es otro). */
export function reloadForNewVersion(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY)) || 0;
    if (Date.now() - last < LOOP_GUARD_MS) return false;
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch {
    // Sin almacenamiento de sesión: se recarga igual (el caso es excepcional).
  }
  window.location.reload();
  return true;
}

/** Carga diferida de un módulo que se recupera de una versión anterior en memoria. */
export async function importFresh<T>(loader: () => Promise<T>): Promise<T> {
  try {
    return await loader();
  } catch (error) {
    if (isStaleChunkError(error) && reloadForNewVersion()) {
      return new Promise<T>(() => {}); // la página se está recargando
    }
    throw error;
  }
}

/** Vite avisa cuando falla la precarga de un archivo (p. ej., la hoja de estilos de una sección). */
export function installStaleVersionReload(): void {
  window.addEventListener("vite:preloadError", (event) => {
    if (reloadForNewVersion()) event.preventDefault();
  });
}
