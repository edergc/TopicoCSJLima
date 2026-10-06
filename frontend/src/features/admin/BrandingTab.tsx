import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImageUp, Palette, RotateCcw, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { BrandMark } from "@/app/layout/BrandMark";
import { api } from "@/shared/api/client";
import type { Branding } from "@/shared/api/types";
import { DEFAULT_BRAND_COLOR, useBranding } from "@/shared/branding/branding";
import { notify } from "@/shared/lib/notify";
import { Button, Callout, Card, CardHeader, Field, Input } from "@/shared/ui";

import { useUpdateParameter } from "./api";

const HEX = /^#[0-9a-fA-F]{6}$/;

/**
 * Identidad visual: logo, color institucional y nombres (interfaz, pantalla de sala, correos y PDF).
 * Debe usarse el logo y los colores del manual de identidad oficial del Poder Judicial.
 */
export function BrandingTab() {
  const branding = useBranding();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const update = useUpdateParameter();
  const [form, setForm] = useState({ color: branding.primary_color, org: branding.org_name, institution: branding.institution_name });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["branding"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-parameters"] });
  };

  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api.put<Branding>("/admin/branding/logo", body);
    },
    onSuccess: () => (notify.success("Logo actualizado", "Ya se muestra en la interfaz, la pantalla de sala y los PDF."), refresh()),
    onError: (e) => notify.error(e),
  });
  const remove = useMutation({
    mutationFn: () => api.delete("/admin/branding/logo"),
    onSuccess: () => (notify.success("Logo eliminado"), refresh()),
    onError: (e) => notify.error(e),
  });

  const save = async () => {
    const changes: [string, string][] = [];
    if (form.color.toLowerCase() !== branding.primary_color) changes.push(["branding.primary_color", form.color.toLowerCase()]);
    if (form.org.trim() !== branding.org_name) changes.push(["branding.org_name", form.org.trim()]);
    if (form.institution.trim() !== branding.institution_name) changes.push(["institution.name", form.institution.trim()]);
    try {
      for (const [key, value] of changes) await update.mutateAsync({ key, value });
      notify.success("Identidad visual guardada");
      refresh();
    } catch (e) {
      notify.error(e);
    }
  };
  const validColor = HEX.test(form.color);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <Card>
        <CardHeader
          title="Identidad visual"
          description="Logo, color institucional y nombres que aparecen en la interfaz, la pantalla de sala, los correos y los reportes PDF."
          icon={<Palette className="size-[18px]" />}
        />
        <div className="space-y-6 p-5">
          <Callout tone="info">
            Use el logo y los colores del <b>manual de identidad visual oficial</b> del Poder Judicial. Formatos: PNG o JPEG de hasta 512 KB
            (preferible PNG con fondo transparente, horizontal o cuadrado).
          </Callout>

          <section>
            <p className="mb-2 text-[0.8125rem] font-medium text-ink">Logo</p>
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg"
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload.mutate(file);
                  e.target.value = "";
                }}
              />
              <Button variant="secondary" icon={<ImageUp className="size-4" />} loading={upload.isPending} onClick={() => fileRef.current?.click()}>
                {branding.logo_updated_at ? "Reemplazar logo" : "Cargar logo"}
              </Button>
              {branding.logo_updated_at && (
                <Button variant="ghost" icon={<Trash2 className="size-4" />} loading={remove.isPending} onClick={() => remove.mutate()}>
                  Quitar logo
                </Button>
              )}
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <Field label="Color institucional" hint="Formato #RRGGBB. Se generan automáticamente los tonos claros y oscuros.">
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  aria-label="Elegir color"
                  value={validColor ? form.color : DEFAULT_BRAND_COLOR}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  className="h-10 w-12 cursor-pointer rounded-lg border border-line-strong bg-panel p-1"
                />
                <Input value={form.color} maxLength={7} onChange={(e) => setForm({ ...form, color: e.target.value.trim() })} className="tabular uppercase" />
                <Button variant="ghost" size="sm" title="Color por defecto" icon={<RotateCcw className="size-4" />} onClick={() => setForm({ ...form, color: DEFAULT_BRAND_COLOR })}>
                  Predeterminado
                </Button>
              </div>
            </Field>
            <div />
            <Field label="Organización">
              <Input value={form.org} maxLength={120} onChange={(e) => setForm({ ...form, org: e.target.value })} />
            </Field>
            <Field label="Institución">
              <Input value={form.institution} maxLength={120} onChange={(e) => setForm({ ...form, institution: e.target.value })} />
            </Field>
          </section>
          <div className="flex justify-end">
            <Button onClick={() => void save()} loading={update.isPending} disabled={!validColor || form.org.trim().length < 3 || form.institution.trim().length < 3}>
              Guardar
            </Button>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Vista previa" description="Encabezado de correos y reportes." />
        <div className="p-5">
          <div className="overflow-hidden rounded-xl ring-1 ring-line">
            <div className="flex items-center gap-3 px-4 py-3 text-white" style={{ background: validColor ? form.color : DEFAULT_BRAND_COLOR }}>
              <BrandMark />
              <div className="min-w-0 leading-tight">
                <p className="truncate text-[0.625rem] tracking-[0.12em] uppercase opacity-80">{form.org}</p>
                <p className="truncate text-sm font-semibold">{form.institution}</p>
                <p className="text-xs opacity-80">Tópico de Salud</p>
              </div>
            </div>
            <div className="space-y-2 bg-panel p-4 text-sm text-ink-muted">
              <p>Estimado(a) Juan:</p>
              <p>Es su turno. Por favor, acérquese al Tópico de Salud.</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
