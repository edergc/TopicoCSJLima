/**
 * Aviso sonoro de la pantalla de turnos: campanilla (Web Audio) + anuncio por voz (Web Speech).
 *
 * Los navegadores bloquean el audio hasta que alguien interactúa con la página; por eso la
 * pantalla muestra "Iniciar pantalla" la primera vez (o se abre Chrome en modo kiosko con
 * --autoplay-policy=no-user-gesture-required, ver manual de despliegue).
 */

let context: AudioContext | null = null;

/** Debe llamarse desde un gesto del usuario (clic) para habilitar el audio. */
export function unlockAudio(): boolean {
  try {
    context ??= new AudioContext();
    void context.resume();
    // Algunos navegadores solo habilitan la voz tras un primer anuncio dentro del gesto.
    if ("speechSynthesis" in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
    return context.state !== "closed";
  } catch {
    return false;
  }
}

export function audioReady(): boolean {
  return context?.state === "running";
}

/** Campanilla de dos tonos ("ding-dong"). */
export function playChime(): Promise<void> {
  if (!context || context.state !== "running") return Promise.resolve();
  const ctx = context;
  const start = ctx.currentTime + 0.05;
  const tones: [number, number][] = [
    [880, 0],
    [659.25, 0.42],
  ];
  for (const [frequency, offset] of tones) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, start + offset);
    gain.gain.exponentialRampToValueAtTime(0.35, start + offset + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 1.1);
    osc.connect(gain).connect(ctx.destination);
    osc.start(start + offset);
    osc.stop(start + offset + 1.2);
  }
  return new Promise((resolve) => window.setTimeout(resolve, 1400));
}

/** "A-047" + "María G." → "Turno A 47. María G. Por favor, acérquese al tópico." */
export function announcementText(ticketCode: string, name: string | null | undefined, place: string): string {
  const match = /^([A-Z]{1,3})-(\d+)$/.exec(ticketCode);
  const ticket = match ? `${match[1]!.split("").join(" ")} ${Number(match[2])}` : ticketCode;
  const who = name ? ` ${name.replace(/\b([A-ZÁÉÍÓÚÑ])\./g, "$1")}.` : "";
  return `Turno ${ticket}.${who} Por favor, acérquese ${place}.`;
}

function spanishVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang.toLowerCase() === "es-pe") ??
    voices.find((v) => v.lang.toLowerCase().startsWith("es-") && /latin|mexic|us|419/i.test(`${v.name} ${v.lang}`)) ??
    voices.find((v) => v.lang.toLowerCase().startsWith("es"))
  );
}

export function speak(text: string): Promise<void> {
  if (!("speechSynthesis" in window)) return Promise.resolve();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-PE";
    const voice = spanishVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 0.92;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
    window.setTimeout(resolve, 12_000); // por si el motor de voz no emite "onend"
  });
}
