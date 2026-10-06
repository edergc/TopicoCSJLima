import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe2, MessageSquareText, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import { api } from "@/shared/api/client";
import type { DisplayMessage } from "@/shared/api/types";
import { useAuth } from "@/shared/auth/AuthProvider";
import { fmt, todayIso } from "@/shared/lib/format";
import { notify } from "@/shared/lib/notify";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, Skeleton, Toggle } from "@/shared/ui";

type Form = { text: string; valid_from: string; valid_to: string; sort_order: number; all_sites: boolean; is_active: boolean };

function status(m: DisplayMessage, today: string): { label: string; tone: "success" | "neutral" | "info" } {
  if (!m.is_active) return { label: "Inactivo", tone: "neutral" };
  if (m.valid_from > today) return { label: `Desde ${fmt.date(m.valid_from)}`, tone: "info" };
  if (m.valid_to && m.valid_to < today) return { label: "Vencido", tone: "neutral" };
  return { label: "Visible", tone: "success" };
}

/** Mensajes que rotan al pie de la pantalla de sala (avisos, campañas de salud). */
export function DisplayMessagesTab({ siteId }: { siteId: number }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const today = todayIso();
  const key = ["display-messages", siteId];
  const { data, isLoading } = useQuery({ queryKey: key, queryFn: () => api.get<DisplayMessage[]>("/display-messages", { site_id: siteId }) });
  const [editing, setEditing] = useState<{ message: DisplayMessage | null; form: Form } | null>(null);
  const canEdit = can("site:configure");
  const canGlobal = can("site:manage");

  const save = useMutation({
    mutationFn: ({ message, form }: { message: DisplayMessage | null; form: Form }) => {
      const body = { text: form.text.trim(), valid_from: form.valid_from, valid_to: form.valid_to || null, sort_order: form.sort_order };
      return message
        ? api.patch<DisplayMessage>(`/display-messages/${message.id}`, { ...body, is_active: form.is_active })
        : api.post<DisplayMessage>("/display-messages", { ...body, site_id: form.all_sites ? null : siteId });
    },
    onSuccess: () => {
      notify.success("Mensaje guardado", "La pantalla de sala lo mostrará en su próxima actualización.");
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["display-messages"] });
    },
    onError: (e) => notify.error(e),
  });

  const form = editing?.form;
  const set = (patch: Partial<Form>) => editing && setEditing({ ...editing, form: { ...editing.form, ...patch } });
  const valid = form !== undefined && form.text.trim().length >= 3 && (!form.valid_to || form.valid_to >= form.valid_from);

  return (
    <Card>
      <CardHeader
        title="Mensajes de la pantalla de sala"
        description="Rotan al pie de la pantalla (avisos, campañas de salud). Si no hay ninguno vigente se muestra el mensaje general de los parámetros."
        icon={<MessageSquareText className="size-[18px]" />}
        actions={
          canEdit && (
            <Button
              size="sm"
              icon={<Plus className="size-4" />}
              onClick={() =>
                setEditing({ message: null, form: { text: "", valid_from: today, valid_to: "", sort_order: (data?.length ?? 0) + 1, all_sites: false, is_active: true } })
              }
            >
              Nuevo mensaje
            </Button>
          )
        }
      />
      {isLoading ? (
        <Skeleton className="m-5 h-24" />
      ) : !data?.length ? (
        <EmptyState icon={MessageSquareText} title="Sin mensajes" description="Ej.: «Lávese las manos antes de ingresar», «Campaña de vacunación el viernes»." />
      ) : (
        <ul>
          {data.map((m) => {
            const st = status(m, today);
            const editable = canEdit && (m.site_id !== null || canGlobal);
            return (
              <li key={m.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-5 py-3 last:border-b-0">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{m.text}</p>
                  <p className="flex flex-wrap items-center gap-2 text-[0.8125rem] text-ink-soft">
                    <Badge tone={st.tone}>{st.label}</Badge>
                    {m.site_id === null && (
                      <span className="inline-flex items-center gap-1">
                        <Globe2 className="size-3.5" aria-hidden /> Todas las sedes
                      </span>
                    )}
                    <span>
                      {fmt.date(m.valid_from)} – {m.valid_to ? fmt.date(m.valid_to) : "sin fin"}
                    </span>
                  </p>
                </div>
                {editable && (
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Pencil className="size-4" />}
                    onClick={() =>
                      setEditing({
                        message: m,
                        form: { text: m.text, valid_from: m.valid_from, valid_to: m.valid_to ?? "", sort_order: m.sort_order, all_sites: m.site_id === null, is_active: m.is_active },
                      })
                    }
                  >
                    Editar
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <Modal
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        dismissable={false}
        title={editing?.message ? "Editar mensaje" : "Nuevo mensaje"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Cancelar
            </Button>
            <Button onClick={() => editing && save.mutate(editing)} loading={save.isPending} disabled={!valid}>
              Guardar
            </Button>
          </>
        }
      >
        {form && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Texto" required className="sm:col-span-2" hint={`${form.text.length}/200 · se recomienda menos de 90 caracteres`}>
              <Input value={form.text} maxLength={200} onChange={(e) => set({ text: e.target.value })} autoFocus />
            </Field>
            <Field label="Visible desde">
              <Input type="date" value={form.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
            </Field>
            <Field label="Hasta (opcional)">
              <Input type="date" min={form.valid_from} value={form.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
            </Field>
            <Field label="Orden">
              <Input type="number" min={0} max={999} value={form.sort_order} onChange={(e) => set({ sort_order: Number(e.target.value) || 0 })} />
            </Field>
            <div className="space-y-3 sm:col-span-2">
              {!editing?.message && canGlobal && (
                <Toggle checked={form.all_sites} onChange={(v) => set({ all_sites: v })} label="Mostrar en todas las sedes" />
              )}
              {editing?.message && <Toggle checked={form.is_active} onChange={(v) => set({ is_active: v })} label="Activo" />}
            </div>
          </div>
        )}
      </Modal>
    </Card>
  );
}
