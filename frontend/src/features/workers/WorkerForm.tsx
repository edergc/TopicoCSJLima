import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { Worker } from "@/shared/api/types";
import { todayIso } from "@/shared/lib/format";
import { errorMessage, notify } from "@/shared/lib/notify";
import { Button, Callout, Field, Input, Modal, Select } from "@/shared/ui";

import { useCreateWorker, useDepartments, useUpdateWorker } from "./api";

const optional = (schema: z.ZodString) => schema.optional().or(z.literal("").transform(() => undefined));

const schema = z.object({
  document_number: z.string().regex(/^\d{8}$/, "El DNI debe tener 8 dígitos."),
  first_names: z.string().trim().min(1, "Obligatorio.").max(100),
  paternal_surname: z.string().trim().min(1, "Obligatorio.").max(80),
  maternal_surname: optional(z.string().trim().max(80)),
  sex: z.enum(["F", "M", ""]).optional(),
  birth_date: optional(z.string()),
  institutional_email: optional(z.string().trim().email("Correo inválido.")),
  phone: optional(z.string().trim().regex(/^\+?[0-9 ]{6,20}$/, "Teléfono inválido.")),
  employee_code: optional(z.string().trim().max(20)),
  department_name: optional(z.string().trim().max(200)),
  coverage_valid_from: optional(z.string()),
});
type FormValues = z.infer<typeof schema>;

export function WorkerFormModal({ worker, open, onClose }: { worker?: Worker; open: boolean; onClose: () => void }) {
  const isEdit = Boolean(worker);
  const departments = useDepartments();
  const create = useCreateWorker();
  const update = useUpdateWorker(worker?.public_id ?? "");
  const mutation = isEdit ? update : create;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      document_number: worker?.document_number ?? "",
      first_names: worker?.first_names ?? "",
      paternal_surname: worker?.paternal_surname ?? "",
      maternal_surname: worker?.maternal_surname ?? "",
      sex: (worker?.sex as "F" | "M" | undefined) ?? "",
      birth_date: worker?.birth_date ?? "",
      institutional_email: worker?.institutional_email ?? "",
      phone: worker?.phone ?? "",
      employee_code: worker?.employee_code ?? "",
      department_name: worker?.department_name ?? "",
      coverage_valid_from: isEdit ? "" : todayIso(),
    },
  });

  const onSubmit = handleSubmit((values) => {
    const common = {
      first_names: values.first_names,
      paternal_surname: values.paternal_surname,
      maternal_surname: values.maternal_surname ?? null,
      sex: values.sex ? values.sex : null,
      birth_date: values.birth_date ?? null,
      institutional_email: values.institutional_email ?? null,
      phone: values.phone ?? null,
      employee_code: values.employee_code ?? null,
      department_name: values.department_name ?? null,
    };
    const onSuccess = () => {
      notify.success(isEdit ? "Datos del trabajador actualizados" : "Trabajador registrado");
      onClose();
    };
    if (isEdit) update.mutate(common, { onSuccess });
    else
      create.mutate(
        { ...common, document_type: "DNI", document_number: values.document_number, coverage_valid_from: values.coverage_valid_from ?? null },
        { onSuccess },
      );
  });

  return (
    <Modal
      open={open}
      onOpenChange={(o) => !o && onClose()}
      size="lg"
      dismissable={false}
      title={isEdit ? "Editar trabajador" : "Registrar trabajador"}
      description="Solo datos administrativos. El alta masiva se realiza por importación del Excel institucional."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" form="worker-form" loading={mutation.isPending}>
            {isEdit ? "Guardar cambios" : "Registrar"}
          </Button>
        </>
      }
    >
      <form id="worker-form" onSubmit={onSubmit} noValidate className="grid gap-4 sm:grid-cols-2">
        {mutation.isError && <Callout tone="danger" className="sm:col-span-2">{errorMessage(mutation.error)}</Callout>}
        <Field label="DNI" required error={errors.document_number?.message}>
          <Input inputMode="numeric" maxLength={8} disabled={isEdit} className="tabular" {...register("document_number")} />
        </Field>
        <Field label="Código de trabajador" error={errors.employee_code?.message}>
          <Input {...register("employee_code")} />
        </Field>
        <Field label="Nombres" required error={errors.first_names?.message} className="sm:col-span-2">
          <Input autoComplete="off" {...register("first_names")} />
        </Field>
        <Field label="Apellido paterno" required error={errors.paternal_surname?.message}>
          <Input autoComplete="off" {...register("paternal_surname")} />
        </Field>
        <Field label="Apellido materno" error={errors.maternal_surname?.message}>
          <Input autoComplete="off" {...register("maternal_surname")} />
        </Field>
        <Field label="Sexo">
          <Select {...register("sex")}>
            <option value="">No especificado</option>
            <option value="F">Femenino</option>
            <option value="M">Masculino</option>
          </Select>
        </Field>
        <Field label="Fecha de nacimiento" hint="La edad se calcula automáticamente.">
          <Input type="date" max={todayIso()} {...register("birth_date")} />
        </Field>
        <Field label="Correo institucional" error={errors.institutional_email?.message}>
          <Input type="email" autoComplete="off" {...register("institutional_email")} />
        </Field>
        <Field label="Teléfono" error={errors.phone?.message}>
          <Input inputMode="tel" autoComplete="off" {...register("phone")} />
        </Field>
        <Field label="Dependencia" className="sm:col-span-2" hint="Seleccione una existente o escriba una nueva.">
          <Input list="departments" autoComplete="off" {...register("department_name")} />
        </Field>
        <datalist id="departments">
          {departments.data?.map((d) => <option key={d.id} value={d.name} />)}
        </datalist>
        {!isEdit && (
          <Field label="Cobertura EPS Rímac desde" hint="Déjelo vacío si aún no está habilitado." className="sm:col-span-2">
            <Input type="date" {...register("coverage_valid_from")} />
          </Field>
        )}
      </form>
    </Modal>
  );
}
