import { DoorOpen } from "lucide-react";

import type { Appointment, RoomStatus } from "@/shared/api/types";
import { Button, Modal } from "@/shared/ui";

interface Props {
  appointment: Appointment;
  /** Consultorios libres (destinos posibles). */
  rooms: RoomStatus[];
  loading: boolean;
  onPick: (roomId: number) => void;
  onClose: () => void;
}

/** Reasignar el consultorio de quien fue llamado o está en atención. */
export function RoomChangeDialog({ appointment, rooms, loading, onPick, onClose }: Props) {
  const called = appointment.status === "LLAMADO";
  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      size="sm"
      title={`Cambiar consultorio · ${appointment.ticket_code}`}
      description={
        called
          ? `Ahora: ${appointment.room_name ?? "sin consultorio"}. La pantalla de sala lo volverá a anunciar con el nuevo consultorio.`
          : `Ahora: ${appointment.room_name ?? "sin consultorio"}. Queda registrado en la línea de tiempo.`
      }
      footer={
        <Button variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
      }
    >
      <div className="grid gap-2">
        {rooms.map((room) => (
          <Button
            key={room.id}
            variant="secondary"
            size="lg"
            className="justify-start"
            loading={loading}
            onClick={() => onPick(room.id)}
            icon={<DoorOpen className="size-5 text-status-done" />}
          >
            {room.name}
            {room.location_note && <span className="ml-2 text-[0.8125rem] font-normal text-ink-soft">{room.location_note}</span>}
          </Button>
        ))}
      </div>
    </Modal>
  );
}
