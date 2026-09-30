import { useQuery } from "@tanstack/react-query";
import { BellRing, CheckCircle2, Clock3, Info, MapPin, Maximize, Minimize, MonitorPlay, Stethoscope, Users, Volume2, VolumeX } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { BrandMark } from "@/app/layout/BrandMark";
import { ApiError, api } from "@/shared/api/client";
import type { DisplayBoard, DisplayTicket } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { fmt } from "@/shared/lib/format";
import { useDocumentTitle, useNow } from "@/shared/lib/hooks";
import { syncServerTime } from "@/shared/lib/serverTime";

import { announcementText, audioReady, playChime, speak, unlockAudio } from "./announcer";

const REFRESH_MS = 4000;
const HIGHLIGHT_MS = 12_000;
const CONTROLS_IDLE_MS = 3000;

/** Un llamado se identifica por turno + número de llamado: volver a llamar también se anuncia. */
const callKey = (t: DisplayTicket) => `${t.ticket_code}#${t.call_count}`;

function useBoard(siteCode: string) {
  return useQuery({
    queryKey: ["display", siteCode],
    queryFn: async ({ signal }) => {
      const sentAt = Date.now();
      const board = await api.get<DisplayBoard>(`/public/display/${encodeURIComponent(siteCode)}`, undefined, signal);
      syncServerTime(board.generated_at, (sentAt + Date.now()) / 2);
      return board;
    },
    refetchInterval: (q) => (q.state.error instanceof ApiError && q.state.error.status === 404 ? false : REFRESH_MS),
    refetchIntervalInBackground: true,
    retry: 1,
    retryDelay: 1500,
  });
}

/**
 * Anuncia cada llamado nuevo, uno a la vez (campanilla + voz) y resalta el turno en pantalla.
 * Los llamados existentes al abrir la pantalla no se anuncian.
 */
function useAnnouncements(board: DisplayBoard | undefined, soundOn: boolean) {
  const seen = useRef<Set<string> | null>(null);
  const pending = useRef<DisplayTicket[]>([]);
  const busy = useRef(false);
  const [highlight, setHighlight] = useState<string | null>(null);
  const settings = useRef({ soundOn, voice: true });
  const voice = board?.voice_enabled ?? true;
  useEffect(() => {
    settings.current = { soundOn, voice };
  }, [soundOn, voice]);

  const drain = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      for (let next = pending.current.shift(); next; next = pending.current.shift()) {
        setHighlight(callKey(next));
        if (settings.current.soundOn && audioReady()) {
          await playChime();
          if (settings.current.voice) await speak(announcementText(next.ticket_code, next.name, "al tópico"));
        } else {
          await new Promise((r) => window.setTimeout(r, 2500));
        }
      }
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    if (!board) return;
    const current = board.calling.map(callKey);
    if (seen.current === null) {
      seen.current = new Set(current);
      return;
    }
    // Más antiguo primero, para anunciarlos en el orden en que fueron llamados.
    const fresh = [...board.calling].reverse().filter((t) => !seen.current!.has(callKey(t)));
    fresh.forEach((t) => seen.current!.add(callKey(t)));
    if (fresh.length) {
      pending.current.push(...fresh);
      void drain();
    }
  }, [board, drain]);

  useEffect(() => {
    if (!highlight) return;
    const id = window.setTimeout(() => setHighlight(null), HIGHLIGHT_MS);
    return () => window.clearTimeout(id);
  }, [highlight]);

  return highlight;
}

/**
 * Cuántas filas de la lista caben completas en su contenedor (la TV puede ser 1080p, 768p…).
 * Las filas sobrantes se ocultan con "invisible" (no se desmontan) para que la medición sea estable.
 */
function useFittingRows(count: number) {
  const [list, setList] = useState<HTMLOListElement | null>(null);
  const [fit, setFit] = useState(count);
  useEffect(() => {
    if (!list) return;
    const measure = () => {
      const rows = Array.from(list.children) as HTMLElement[];
      setFit(rows.filter((row) => row.offsetTop + row.offsetHeight <= list.clientHeight + 1).length);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [list, count]);
  return [setList, Math.min(fit, count)] as const;
}

/** Muestra los controles y el cursor solo mientras se mueve el mouse (la TV queda limpia). */
function useIdle(ms: number): boolean {
  const [idle, setIdle] = useState(false);
  useEffect(() => {
    let id = window.setTimeout(() => setIdle(true), ms);
    const wake = () => {
      setIdle(false);
      window.clearTimeout(id);
      id = window.setTimeout(() => setIdle(true), ms);
    };
    window.addEventListener("pointermove", wake);
    window.addEventListener("keydown", wake);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("pointermove", wake);
      window.removeEventListener("keydown", wake);
    };
  }, [ms]);
  return idle;
}

function useFullscreen() {
  const [active, setActive] = useState(() => Boolean(document.fullscreenElement));
  useEffect(() => {
    const onChange = () => setActive(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggle = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.().catch(() => undefined);
  };
  return { active, toggle };
}

/** Evita que la TV entre en reposo (solo disponible en HTTPS/localhost; en HTTP se ignora). */
function useWakeLock(enabled: boolean) {
  useEffect(() => {
    if (!enabled || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    const request = () => {
      navigator.wakeLock
        .request("screen")
        .then((l) => (lock = l))
        .catch(() => undefined);
    };
    request();
    const onVisible = () => document.visibilityState === "visible" && request();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      void lock?.release().catch(() => undefined);
    };
  }, [enabled]);
}

export default function DisplayPage() {
  const { siteCode = "" } = useParams();
  const { data, error, isError, dataUpdatedAt } = useBoard(siteCode);
  const [started, setStarted] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const highlight = useAnnouncements(data, soundOn && started);
  const idle = useIdle(CONTROLS_IDLE_MS);
  const fullscreen = useFullscreen();
  const now = useNow(1000);
  useWakeLock(started);
  const [waitingListRef, waitingFit] = useFittingRows(data?.waiting.length ?? 0);
  useDocumentTitle(data ? `Pantalla de turnos · ${data.site.short_name}` : "Pantalla de turnos");

  // En modo kiosko (autoplay permitido) no hace falta el clic inicial.
  useEffect(() => {
    unlockAudio();
    const id = window.setTimeout(() => audioReady() && setStarted(true), 400);
    return () => window.clearTimeout(id);
  }, []);

  const start = (withSound: boolean) => {
    if (withSound) unlockAudio();
    setSoundOn(withSound);
    setStarted(true);
    if (!document.fullscreenElement) fullscreen.toggle();
  };

  if (isError && !data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <Shell>
        <div className="grid flex-1 place-items-center p-8 text-center">
          <div className="max-w-xl">
            <MonitorPlay className="mx-auto size-16 text-white/40" aria-hidden />
            <h1 className="mt-6 text-4xl font-semibold">{notFound ? error.message : "Conectando con el servidor…"}</h1>
            <p className="mt-3 text-lg text-white/60">
              {notFound ? "Verifique la dirección de la pantalla." : "La pantalla se actualizará automáticamente."}
            </p>
            {notFound && (
              <Link to="/pantalla" className="mt-8 inline-block rounded-xl bg-white/10 px-5 py-3 font-medium ring-1 ring-white/20 hover:bg-white/15">
                Elegir sede
              </Link>
            )}
          </div>
        </div>
      </Shell>
    );
  }

  const main = data?.calling[0];
  const otherCalls = data?.calling.slice(1, 3) ?? [];
  const online = !isError;

  return (
    <Shell className={cn(idle && started && "cursor-none")}>
      {/* Encabezado */}
      <header className="flex items-center gap-4 border-b border-white/10 bg-black/15 px-[3vw] py-[1.6vh]">
        <BrandMark className="size-[clamp(2.5rem,4.2vw,4.5rem)] rounded-2xl [&_svg]:size-1/2" />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-[clamp(0.7rem,0.95vw,1.05rem)] font-semibold tracking-[0.22em] text-brand-200 uppercase">
            Tópico de Salud · Corte Superior de Justicia de Lima
          </p>
          <p className="truncate text-[clamp(1.1rem,2vw,2.3rem)] font-semibold">{data?.site.name ?? "Cargando…"}</p>
        </div>
        <div className="text-right leading-tight">
          <p className="tabular text-[clamp(1.5rem,3vw,3.4rem)] font-semibold">{fmt.time(now)}</p>
          {data && <p className="text-[clamp(0.75rem,1vw,1.15rem)] text-white/60">{fmt.longDate(data.service_date)}</p>}
        </div>
        <span
          className={cn(
            "ml-2 hidden items-center gap-2 rounded-full px-3 py-1.5 text-[clamp(0.65rem,0.8vw,0.95rem)] font-semibold tracking-widest uppercase ring-1 sm:inline-flex",
            online ? "bg-emerald-400/10 text-emerald-300 ring-emerald-300/30" : "bg-amber-400/10 text-amber-300 ring-amber-300/30",
          )}
          role="status"
        >
          <span className={cn("size-2 rounded-full", online ? "animate-pulse bg-emerald-400" : "bg-amber-400")} />
          {online ? "En línea" : "Reconectando"}
        </span>
      </header>

      {/* Contenido */}
      <main className="grid min-h-0 flex-1 gap-[2vw] px-[3vw] py-[3vh] lg:grid-cols-[1.45fr_1fr]">
        <section
          key={main ? callKey(main) : "idle"}
          aria-live="assertive"
          className={cn(
            "relative flex min-h-0 flex-col overflow-hidden rounded-[2rem] bg-white/[0.06] p-[3vw] ring-1 ring-white/10",
            main && highlight === callKey(main) && "animate-display-flash",
          )}
        >
          {main ? (
            <>
              <p className="flex items-center gap-3 text-[clamp(1rem,1.6vw,1.9rem)] font-semibold tracking-[0.3em] text-amber-300 uppercase">
                <BellRing className={cn("size-[1.2em]", highlight === callKey(main) && "animate-bounce")} aria-hidden />
                Llamando
              </p>
              <div className="flex flex-1 flex-col justify-center">
                <p className="bg-gradient-to-b from-white to-brand-200 bg-clip-text text-[clamp(5rem,15vw,17rem)] leading-[0.95] font-bold tracking-tight text-transparent">
                  {main.ticket_code}
                </p>
                {main.name && <p className="mt-[1.5vh] truncate text-[clamp(2rem,4.4vw,5rem)] font-semibold">{main.name}</p>}
              </div>
              <div className="flex flex-wrap items-center gap-3 text-[clamp(0.95rem,1.4vw,1.6rem)]">
                <span className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-2 font-semibold text-brand-900">
                  <Stethoscope className="size-[1.1em]" aria-hidden /> Acérquese al tópico
                </span>
                {data?.site.location_note && (
                  <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-5 py-2 text-white/85 ring-1 ring-white/15">
                    <MapPin className="size-[1.1em]" aria-hidden /> {data.site.location_note}
                  </span>
                )}
              </div>
            </>
          ) : (
            <IdleMessage board={data} />
          )}
        </section>

        <aside className="flex min-h-0 flex-col gap-[2vh]">
          {(otherCalls.length > 0 || (data?.in_service.length ?? 0) > 0) && (
            <ul className="grid gap-[1.2vh]">
              {otherCalls.map((t) => (
                <TicketRow key={callKey(t)} ticket={t} tone="called" />
              ))}
              {data?.in_service.slice(0, 2).map((t) => (
                <TicketRow key={t.ticket_code} ticket={t} tone="service" />
              ))}
            </ul>
          )}
          <div className="flex min-h-0 flex-1 flex-col rounded-[2rem] bg-white/[0.04] p-[1.6vw] ring-1 ring-white/10">
            <p className="mb-[1.5vh] flex items-center justify-between text-[clamp(0.8rem,1.1vw,1.3rem)] font-semibold tracking-[0.3em] text-white/60 uppercase">
              <span>Siguientes</span>
              {data && data.waiting_total > 0 && <span className="tracking-normal normal-case">{data.waiting_total} en espera</span>}
            </p>
            {data && data.waiting.length === 0 ? (
              <p className="grid flex-1 place-items-center text-center text-[clamp(1rem,1.5vw,1.7rem)] text-white/45">
                No hay personas en espera
              </p>
            ) : (
              <ol ref={waitingListRef} className="relative grid min-h-0 flex-1 content-start gap-[1.2vh] overflow-hidden">
                {data?.waiting.map((t, i) => (
                  <TicketRow key={t.ticket_code} ticket={t} position={i + 1} hidden={i >= waitingFit} />
                ))}
              </ol>
            )}
            {data && data.waiting_total > waitingFit && data.waiting.length > 0 && (
              <p className="mt-[1.5vh] text-center text-[clamp(0.85rem,1.1vw,1.3rem)] text-white/50">
                y {data.waiting_total - waitingFit} más en espera
              </p>
            )}
          </div>
        </aside>
      </main>

      {/* Pie */}
      <footer className="relative flex items-center gap-6 border-t border-white/10 bg-black/20 px-[3vw] py-[1.8vh] text-[clamp(0.85rem,1.25vw,1.45rem)]">
        <p className="flex min-w-0 flex-1 items-center gap-3 text-white/80">
          <Info className="size-[1.2em] shrink-0 text-brand-200" aria-hidden />
          <span className="truncate">{data?.message}</span>
        </p>
        {data && (
          <div className="hidden items-center gap-6 text-white/65 md:flex">
            <span className="inline-flex items-center gap-2">
              <Users className="size-[1.1em]" aria-hidden /> En espera <b className="tabular text-white">{data.waiting_total}</b>
            </span>
            <span className="inline-flex items-center gap-2">
              <CheckCircle2 className="size-[1.1em]" aria-hidden /> Atendidos hoy <b className="tabular text-white">{data.attended_count}</b>
            </span>
          </div>
        )}
        {dataUpdatedAt > 0 && (
          <span
            key={dataUpdatedAt}
            className="animate-refresh-bar absolute inset-x-0 bottom-0 h-[3px] origin-left bg-gradient-to-r from-brand-500 via-amber-300 to-brand-500"
            style={{ animationDuration: `${REFRESH_MS}ms` }}
            aria-hidden
          />
        )}
      </footer>

      {/* Controles (visibles al mover el mouse) */}
      {started && (
        <div
          className={cn(
            "fixed top-[12vh] right-[3vw] flex gap-2 transition-opacity duration-300",
            idle ? "pointer-events-none opacity-0" : "opacity-100",
          )}
        >
          <ControlButton
            label={soundOn ? "Silenciar" : "Activar sonido"}
            onClick={() => {
              if (!soundOn) unlockAudio();
              setSoundOn(!soundOn);
            }}
          >
            {soundOn ? <Volume2 className="size-5" /> : <VolumeX className="size-5" />}
          </ControlButton>
          <ControlButton label={fullscreen.active ? "Salir de pantalla completa" : "Pantalla completa"} onClick={fullscreen.toggle}>
            {fullscreen.active ? <Minimize className="size-5" /> : <Maximize className="size-5" />}
          </ControlButton>
        </div>
      )}

      {!started && (
        <div className="fixed inset-0 z-10 grid place-items-center bg-black/60 p-6 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl bg-brand-900 p-8 text-center shadow-2xl ring-1 ring-white/15">
            <MonitorPlay className="mx-auto size-14 text-brand-200" aria-hidden />
            <h1 className="mt-4 text-2xl font-semibold">Pantalla de turnos</h1>
            <p className="mt-2 text-white/65">
              {data?.site.name ?? "Cargando sede…"}. Al iniciar, la pantalla pasa a modo completo y anuncia cada llamado con sonido.
            </p>
            <button
              type="button"
              autoFocus
              onClick={() => start(true)}
              className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber-300 px-5 py-3.5 text-lg font-semibold text-brand-900 hover:bg-amber-200"
            >
              <Volume2 className="size-5" aria-hidden /> Iniciar pantalla
            </button>
            <button type="button" onClick={() => start(false)} className="mt-3 text-sm text-white/60 underline-offset-4 hover:text-white hover:underline">
              Iniciar sin sonido
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "flex h-dvh flex-col overflow-hidden bg-[radial-gradient(ellipse_at_top_left,#7a1e2c_0%,#45111a_42%,#1c080c_100%)] text-white antialiased select-none",
        className,
      )}
    >
      {children}
    </div>
  );
}

function IdleMessage({ board }: { board: DisplayBoard | undefined }) {
  let title = "Espere su llamado";
  let detail = "El número de su turno aparecerá aquí cuando sea su momento.";
  if (board?.day_status === "CLOSED") {
    title = "Atención del día finalizada";
    detail = "Gracias por su visita.";
  } else if (board && !board.day_status) {
    title = "Aún no hay turnos registrados hoy";
    detail = "Solicite su turno en el tópico.";
  } else if (board?.in_service.length) {
    title = "En atención";
    detail = "En breve se llamará al siguiente turno.";
  }
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      <Clock3 className="size-[clamp(3rem,6vw,7rem)] text-white/25" aria-hidden />
      <p className="mt-[3vh] text-[clamp(2rem,4vw,4.5rem)] font-semibold">{title}</p>
      <p className="mt-[1.5vh] text-[clamp(1rem,1.6vw,1.9rem)] text-white/55">{detail}</p>
    </div>
  );
}

function TicketRow({
  ticket,
  position,
  tone,
  hidden = false,
}: {
  ticket: DisplayTicket;
  position?: number;
  tone?: "called" | "service";
  hidden?: boolean;
}) {
  return (
    <li
      aria-hidden={hidden || undefined}
      className={cn(
        hidden && "invisible",
        "flex list-none items-center gap-[1.2vw] rounded-2xl px-[1.3vw] py-[1.4vh] ring-1",
        tone === "called" && "bg-amber-300/12 ring-amber-300/35",
        tone === "service" && "bg-white/[0.08] ring-white/15",
        !tone && "bg-white/[0.07] ring-white/10",
      )}
    >
      {position !== undefined && (
        <span className="tabular grid size-[clamp(1.8rem,2.4vw,2.8rem)] shrink-0 place-items-center rounded-full bg-white/10 text-[clamp(0.8rem,1vw,1.2rem)] font-semibold text-white/70">
          {position}
        </span>
      )}
      <span className="text-[clamp(1.3rem,2.2vw,2.6rem)] font-bold tracking-tight">{ticket.ticket_code}</span>
      <span className="min-w-0 flex-1 truncate text-[clamp(1rem,1.6vw,1.9rem)] text-white/80">{ticket.name}</span>
      {tone === "called" && <span className="text-[clamp(0.75rem,1vw,1.15rem)] font-semibold tracking-widest text-amber-300 uppercase">Llamado</span>}
      {tone === "service" && <span className="text-[clamp(0.75rem,1vw,1.15rem)] font-semibold tracking-widest text-white/60 uppercase">En atención</span>}
      {!tone && ticket.estimated_at && (
        <span className="tabular text-[clamp(0.85rem,1.2vw,1.4rem)] text-white/55">≈ {fmt.time(ticket.estimated_at)}</span>
      )}
    </li>
  );
}

function ControlButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="grid size-11 place-items-center rounded-xl bg-black/40 text-white ring-1 ring-white/20 backdrop-blur hover:bg-black/60"
    >
      {children}
    </button>
  );
}
