import { useState } from "react";

import type { Room } from "@/shared/api/types";

const key = (siteId: number) => `topico.room.${siteId}`;

function read(siteId: number | undefined): number | null {
  if (siteId === undefined) return null;
  try {
    const value = Number(localStorage.getItem(key(siteId)));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

/**
 * Consultorio desde el que trabaja la encargada en este equipo (por sede).
 * Con un solo consultorio activo se usa ese; un consultorio guardado que ya no está activo se ignora.
 */
export function useWorkingRoom(siteId: number | undefined, activeRooms: Room[]): [number | null, (id: number | null) => void] {
  const [stored, setStored] = useState<Record<number, number | null>>({});
  const saved = siteId === undefined ? null : siteId in stored ? stored[siteId]! : read(siteId);
  const valid = activeRooms.some((r) => r.id === saved) ? saved : null;
  const roomId = activeRooms.length === 1 ? activeRooms[0]!.id : valid;

  const setRoomId = (id: number | null) => {
    if (siteId === undefined) return;
    setStored((prev) => ({ ...prev, [siteId]: id }));
    try {
      if (id === null) localStorage.removeItem(key(siteId));
      else localStorage.setItem(key(siteId), String(id));
    } catch {
      /* almacenamiento no disponible: se mantiene en memoria */
    }
  };
  return [roomId, setRoomId];
}
