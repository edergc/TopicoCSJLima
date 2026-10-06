import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DoorOpen, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import { keys, useRooms } from "@/features/appointments/api";
import { api } from "@/shared/api/client";
import type { Room } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, Skeleton, Toggle } from "@/shared/ui";

type Form = { name: string; location_note: string; sort_order: number; is_active: boolean };

/** Consultorios del tópico: la encargada llama a cada persona a un consultorio (se muestra en la pantalla de sala). */
export function RoomsTab({ siteId }: { siteId: number }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading } = useRooms(siteId);
  const [editing, setEditing] = useState<{ room: Room | null; form: Form } | null>(null);
  const canEdit = can("site:configure");

  const save = useMutation({
    mutationFn: ({ room, form }: { room: Room | null; form: Form }) => {
      const body = { name: form.name.trim(), location_note: form.location_note.trim() || null, sort_order: form.sort_order };
      return room
        ? api.patch<Room>(`/sites/${siteId}/rooms/${room.id}`, { ...body, is_active: form.is_active })
        : api.post<Room>(`/sites/${siteId}/rooms`, body);
    },
    onSuccess: (_r, vars) => {
      notify.success(vars.room ? "Consultorio actualizado" : "Consultorio registrado");
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: keys.rooms(siteId) });
    },
    onError: (e) => notify.error(e),
  });

  const form = editing?.form;
  const set = (patch: Partial<Form>) => editing && setEditing({ ...editing, form: { ...editing.form, ...patch } });
  const nextOrder = (data?.length ?? 0) + 1;

  return (
    <Card>
      <CardHeader
        title="Consultorios del tópico"
        description="Al llamar, la persona ve en la pantalla de sala (y en el correo) a qué consultorio acercarse. Con un solo consultorio activo se asigna automáticamente."
        icon={<DoorOpen className="size-[18px]" />}
        actions={
          canEdit && (
            <Button
              size="sm"
              icon={<Plus className="size-4" />}
              onClick={() => setEditing({ room: null, form: { name: `Consultorio ${nextOrder}`, location_note: "", sort_order: nextOrder, is_active: true } })}
            >
              Registrar consultorio
            </Button>
          )
        }
      />
      {isLoading ? (
        <Skeleton className="m-5 h-24" />
      ) : !data?.length ? (
        <EmptyState
          icon={DoorOpen}
          title="Sin consultorios registrados"
          description="Mientras no haya consultorios, la pantalla de sala indica «Acérquese al tópico»."
        />
      ) : (
        <ul>
          {data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-5 py-3 last:border-b-0">
              <span className="grid size-9 place-items-center rounded-full bg-brand-50 text-brand-700">
                <DoorOpen className="size-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">
                  {r.name} {!r.is_active && <Badge className="ml-1">Inactivo</Badge>}
                </p>
                <p className="text-[0.8125rem] text-ink-soft">{r.location_note || "—"}</p>
              </div>
              {canEdit && (
                <Button size="sm" variant="ghost" icon={<Pencil className="size-4" />} onClick={() => setEditing({ room: r, form: { name: r.name, location_note: r.location_note ?? "", sort_order: r.sort_order, is_active: r.is_active } })}>
                  Editar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        dismissable={false}
        size="sm"
        title={editing?.room ? "Editar consultorio" : "Registrar consultorio"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Cancelar
            </Button>
            <Button onClick={() => editing && save.mutate(editing)} loading={save.isPending} disabled={!form || form.name.trim().length < 2}>
              Guardar
            </Button>
          </>
        }
      >
        {form && (
          <div className="grid gap-4">
            <Field label="Nombre" required hint="Como se mostrará en la pantalla de sala, p. ej. «Consultorio 1».">
              <Input value={form.name} maxLength={60} onChange={(e) => set({ name: e.target.value })} autoFocus />
            </Field>
            <Field label="Ubicación" hint="Opcional, p. ej. «Primer piso, al fondo». Se incluye en el correo de llamado.">
              <Input value={form.location_note} maxLength={150} onChange={(e) => set({ location_note: e.target.value })} />
            </Field>
            <Field label="Orden">
              <Input type="number" min={0} max={999} value={form.sort_order} onChange={(e) => set({ sort_order: Number(e.target.value) || 0 })} />
            </Field>
            {editing?.room && (
              <Toggle
                checked={form.is_active}
                onChange={(v) => set({ is_active: v })}
                label="Activo"
                description="Un consultorio inactivo no se puede usar en nuevos llamados."
              />
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
}
