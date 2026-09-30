/**
 * Cliente HTTP de la API.
 *
 * Seguridad:
 *  - El access token vive SOLO en memoria (nunca en localStorage: mitiga robo por XSS).
 *  - La sesión se renueva con la cookie HttpOnly del refresh token (inaccesible a JS).
 *  - Si varias solicitudes reciben 401 a la vez, se hace UNA sola renovación (single-flight).
 */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details: unknown = null, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Errores de validación campo por campo que devuelve el backend. */
  get fieldErrors(): { field: string; message: string }[] {
    return Array.isArray(this.details) ? (this.details as { field: string; message: string }[]) : [];
  }
}

type Listener = () => void;

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
const sessionExpiredListeners = new Set<Listener>();
const tokenListeners = new Set<(payload: unknown) => void>();

export const session = {
  getToken: () => accessToken,
  setToken(token: string | null) {
    accessToken = token;
  },
  /** Se notifica cuando la sesión no puede renovarse (hay que volver a iniciar sesión). */
  onExpired(listener: Listener) {
    sessionExpiredListeners.add(listener);
    return () => sessionExpiredListeners.delete(listener);
  },
  /** Se notifica con el cuerpo de /auth/refresh cada vez que la sesión se renueva. */
  onRefreshed(listener: (payload: unknown) => void) {
    tokenListeners.add(listener);
    return () => tokenListeners.delete(listener);
  },
};

const NETWORK_ERROR = new ApiError(
  0,
  "NETWORK_ERROR",
  "No se pudo conectar con el servidor. Verifique su conexión a la red institucional.",
);

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
  /** No intentar renovar la sesión ante un 401 (endpoints de autenticación). */
  skipRefresh?: boolean;
}

function buildUrl(path: string, query?: Query): string {
  const url = `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  try {
    const body = (await response.json()) as { code?: string; message?: string; details?: unknown };
    return new ApiError(
      response.status,
      body.code ?? "UNKNOWN",
      body.message ?? "Ocurrió un error inesperado.",
      body.details ?? null,
      requestId,
    );
  } catch {
    return new ApiError(response.status, "UNKNOWN", "Ocurrió un error inesperado.", null, requestId);
  }
}

async function rawFetch(method: string, path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  try {
    return await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      signal: options.signal,
      credentials: "same-origin",
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw NETWORK_ERROR;
  }
}

/** Renueva el access token usando la cookie de refresh. Una sola renovación a la vez. */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await rawFetch("POST", "/auth/refresh", { skipRefresh: true });
      if (!response.ok) {
        accessToken = null;
        return false;
      }
      const payload = (await response.json()) as { access_token: string };
      accessToken = payload.access_token;
      tokenListeners.forEach((listener) => listener(payload));
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

const REFRESHABLE = new Set(["TOKEN_EXPIRED", "TOKEN_INVALID", "UNAUTHORIZED"]);

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  let response = await rawFetch(method, path, options);

  if (response.status === 401 && !options.skipRefresh) {
    const error = await toApiError(response.clone());
    if (REFRESHABLE.has(error.code)) {
      if (await refreshSession()) {
        response = await rawFetch(method, path, options);
      } else {
        sessionExpiredListeners.forEach((listener) => listener());
        throw new ApiError(401, "SESSION_EXPIRED", "Su sesión ha finalizado. Inicie sesión nuevamente.");
      }
    }
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Descarga un archivo (exportaciones) respetando la autenticación. */
async function download(path: string, query?: Query, fallbackName = "descarga"): Promise<void> {
  let response = await rawFetch("GET", path, { query });
  if (response.status === 401 && (await refreshSession())) response = await rawFetch("GET", path, { query });
  if (!response.ok) throw await toApiError(response);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: match?.[1] ?? fallbackName });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>("GET", path, { query, signal }),
  post: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "body"> = {}) =>
    request<T>("POST", path, { ...options, body }),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
  download,
};
