# Manual de usuario

**Sistema de Gestión de Atención del Tópico de Salud — Corte Superior de Justicia de Lima**

Contenido:
1. Ingreso al sistema
2. Encargada del tópico: la Mesa de atención
3. Consulta del turno (para trabajadores)
4. Supervisión: reportes, sedes y horarios
5. Administración
6. Auditoría
7. Preguntas frecuentes

---

## 1. Ingreso al sistema

1. Abra el navegador (Edge o Chrome) e ingrese la dirección que le indicó TI, por ejemplo `https://<servidor>:42000`.
2. Escriba su **usuario** y su **contraseña** y pulse **Ingresar**.
3. **La primera vez**, el sistema le pedirá definir una contraseña personal: al menos 10 caracteres, con letras y números, y sin su nombre de usuario.

![Inicio de sesión](manual/img/01-login.png)

- Tras 5 intentos fallidos la cuenta se bloquea 15 minutos. Si lo necesita antes, el administrador puede desbloquearla.
- Por seguridad, la sesión dura como máximo una jornada. Para salir use el menú con su nombre (arriba a la derecha) → **Cerrar sesión**.
- Si trabaja en más de una sede, elija la **sede de trabajo** en la parte superior de la pantalla.

---

## 2. Encargada del tópico: la Mesa de atención

La Mesa de atención reúne todo lo necesario para la operación del día.

![Mesa de atención](manual/img/02-mesa.png)

| Zona | Qué muestra |
|---|---|
| Indicadores (arriba) | Cupos **disponibles**, registrados, en espera, en curso (llamados y en atención), atendidos y cerrados |
| Registrar atención (izquierda) | Búsqueda por DNI y registro del turno |
| En atención / Llamados | Quién está siendo atendido y a quién se llamó (con la cuenta regresiva de tolerancia) |
| **LLAMAR SIGUIENTE** | Llama al siguiente turno en orden de registro |
| En espera | La cola, en orden, con la hora estimada referencial |

La pantalla se actualiza sola cada pocos segundos.

### 2.1 Registrar una atención (llamada telefónica o presencial)

1. Pulse **F2** (o haga clic en el campo DNI) y escriba los **8 dígitos** del DNI.
2. El sistema verifica automáticamente al trabajador:
   - ✅ **Habilitado · EPS Rímac vigente**: puede registrarlo.
   - ❌ **No habilitado**: no existe, está inactivo o no tiene cobertura EPS Rímac. No se puede registrar.
   - ⚠️ **Ya tiene turno**: se muestra su turno actual.
   - También indica si el trabajador **tiene correo**: si no lo tiene, no recibirá avisos, así que infórmele su turno de palabra.

   ![Verificación por DNI](manual/img/03-mesa-dni.png)

3. Indique el **canal**: *Teléfono* o *Presencial*.
4. Opcionalmente, agregue una **observación administrativa**.

   > ⚠️ **No registre síntomas, diagnósticos ni información clínica.** El sistema es administrativo.

5. Pulse **Registrar turno**. Aparece el **turno generado** en grande, con la posición y la hora estimada: díctelos al trabajador.

![Turno registrado](manual/img/17-turno-registrado.png)

**Mensajes que puede ver:**

| Mensaje | Significado |
|---|---|
| "Se ha alcanzado la capacidad máxima de atención…" | No quedan cupos para hoy en la sede |
| "El horario de registro de atenciones para hoy ha concluido" | Se superó la hora de cierre de registros |
| "El tópico de esta sede no atiende en la fecha seleccionada" | Día marcado como cerrado (feriado u otro motivo) |
| "Según la configuración de la sede, el trabajador no puede volver a registrarse hoy" | Ya se le marcó como no presentado hoy |

### 2.2 Llamar, atender y finalizar

1. Pulse **LLAMAR SIGUIENTE**, o la tecla **F4**. El siguiente turno pasa a **Llamado** y, si tiene correo, recibe el aviso "acérquese al tópico". Puede además llamarlo por teléfono.
2. Cuando el trabajador llega, pulse **Iniciar atención** (estado **En atención**).
3. Al terminar, pulse **Finalizar atención** (estado **Atendido**).

Por defecto solo puede haber **una atención en curso** a la vez por sede (un médico). Finalice la actual antes de iniciar otra.

### 2.3 Si el trabajador no llega

- En la tarjeta del llamado se ve la **tolerancia** (p. ej., "tolerancia 06:56").
- Cuando vence, se habilita **No se presentó**, que libera el cupo.
- Si el trabajador avisa que llegará más tarde, use **⋯ → Devolver a la cola**: conserva su número y su lugar.

### 2.4 Cancelar o anular

Desde el botón **⋯** de cada turno:

| Acción | Cuándo usarla | Efecto |
|---|---|---|
| **Cancelar** | El trabajador ya no requiere la atención (p. ej., "me atenderé en una clínica") | Libera el cupo; se registra el motivo |
| **Anular** | **Error de registro** (persona o sede equivocada, duplicado) | Libera el cupo; no cuenta como demanda en los reportes |

Ambas piden un **motivo**. Si elige "Otro motivo", debe escribir una observación.

![Cancelar atención](manual/img/18-cancelar.png)

Ningún registro se elimina: todo queda en el historial.

### 2.5 Estados de una atención

| Estado | Significado |
|---|---|
| 📝 **Registrado** | Solicitud para una fecha futura |
| ⏳ **En espera** | En la cola del día |
| 🔔 **Llamado** | Se le pidió acercarse al tópico |
| 🩺 **En atención** | Está siendo atendido |
| ✅ **Atendido** | Atención concluida |
| ✖ **Cancelado** | El trabajador desistió; cupo liberado |
| ⊘ **No presentado** | No acudió tras el llamado; cupo liberado |
| ⌫ **Anulado** | Error de registro; cupo liberado |

### 2.6 Historial y detalle

En **Atenciones** puede buscar por fecha, estado, sede o DNI. Al hacer clic en una atención verá su **línea de tiempo** (quién hizo cada acción y cuándo) y los **correos** enviados. Desde ahí puede reenviar un correo.

![Detalle de atención](manual/img/06-atencion-detalle.png)

### 2.7 Atajos de teclado

| Tecla | Acción |
|---|---|
| **F2** | Ir al campo DNI |
| **F4** | Llamar siguiente |
| **Esc** | Cerrar ventana o diálogo |

---

## 3. Consulta del turno (para trabajadores)

Los trabajadores pueden ver el estado de su turno desde su celular o PC en `https://<servidor>:42000/consulta`, ingresando su **DNI** y el **código de turno** (p. ej., A-011).

Verán su posición, cuántas personas tienen delante y la hora aproximada. Por privacidad, la consulta no muestra datos de otras personas.

![Consulta del turno](manual/img/16-consulta-movil.png)

---

## 4. Supervisión

### 4.1 Reportes

**Reportes** muestra los indicadores del periodo elegido (7, 30 o 90 días, o un rango personalizado):
- solicitudes, atendidos, uso de cupos, inasistencia, espera promedio y duración promedio;
- resultado diario frente a la capacidad, demanda por hora y dependencias con más solicitudes;
- tabla detallada por día y sede.

Con permiso de exportación, el botón **Exportar** genera un Excel o un CSV. El **listado nominal** (con datos personales) requiere un permiso adicional y queda registrado en la auditoría.

![Reportes](manual/img/07-reportes.png)

### 4.2 Sedes y horarios

En **Sedes y horarios** (para la sede elegida arriba):
- **Configuración:** capacidad diaria, duración de turno, tolerancia, atenciones simultáneas, avisos por correo y reglas de re-registro. Los cambios se **programan desde una fecha futura**: el día en curso no se altera.
- **Horario:** bloques de mañana y tarde por día de la semana.
- **Cierres:** feriados o días sin atención; bloquean el registro en esas fechas.
- **Capacidad del día:** ajuste puntual de un día (p. ej., el médico atenderá medio turno), con motivo obligatorio.
- **Datos de la sede:** nombre y ubicación del tópico (aparece en los correos de llamado).

![Configuración de sede](manual/img/08-sedes.png)

---

## 5. Administración

### 5.1 Usuarios y roles

- **Nuevo usuario:** usuario, nombre, correo, **roles** y **sedes autorizadas**. El sistema genera una **contraseña temporal** que se muestra **una sola vez**: entréguela de forma segura.
- Desde la lista puede **restablecer** la contraseña, **desbloquear** o **desactivar** una cuenta.
- La pestaña **Roles y permisos** permite ajustar qué puede hacer cada rol. Todo cambio queda auditado.

| Rol | Uso típico |
|---|---|
| Encargado(a) del tópico | Opera la mesa de su sede |
| Supervisor(a) | Opera, configura su sede, ve y exporta reportes |
| Administrador(a) | Usuarios, roles, importaciones, catálogos y parámetros (no opera la cola) |
| Auditor(a) | Solo consulta la auditoría y los reportes |

![Usuarios](manual/img/12-usuarios.png)

### 5.2 Trabajadores e importación

- **Trabajadores:** búsqueda por DNI o nombre, ficha, alta manual, edición y cobertura EPS. Cada consulta de ficha queda registrada, porque se trata de un dato personal.
- **Importaciones**, para actualizar la relación de EPS Rímac desde el Excel institucional:
  1. Arrastre o seleccione el archivo **.xlsx**.
  2. Revise el resultado: **nuevos**, **actualizan**, **sin cambios**, **duplicados** y **errores**, fila por fila. Puede descargar el reporte de observaciones.
  3. Pulse **Confirmar importación**. Solo si el archivo es la relación **completa** vigente, active *"Terminar la cobertura de quienes no figuran"*.

  Nada se incorpora hasta confirmar. El mismo archivo no puede importarse dos veces.

![Importaciones](manual/img/11-importaciones.png)

### 5.3 Catálogos y parámetros

- **Motivos:** textos ofrecidos al cancelar, anular, etc. Pueden desactivarse sin perder el historial.
- **Plantillas de correo:** editables, con variables (`{{ ticket_code }}`, etc.) y **vista previa**.
- **Parámetros:** valores generales, como los intentos de ingreso, el tiempo de bloqueo y los días de anticipación.

![Plantillas](manual/img/14-plantillas.png)

---

## 6. Auditoría

**Auditoría** registra cada acción relevante: quién, cuándo, desde qué IP, sobre qué registro, y los valores anteriores y nuevos. Se puede filtrar por fecha, usuario, acción, resultado y sede.

El botón **Verificar integridad** comprueba que ningún evento haya sido alterado o eliminado: cada evento está encadenado criptográficamente con el anterior.

![Auditoría](manual/img/15-auditoria.png)

---

## 7. Preguntas frecuentes

**¿Puedo registrar a alguien que no aparece como habilitado?**
No. Solo se registran trabajadores con EPS Rímac vigente. Si debería estar habilitado, el administrador debe actualizar la relación (Importaciones) o su ficha (Trabajadores).

**Un trabajador canceló por error. ¿Puedo revertirlo?**
No: los estados finales no se modifican. Registre una nueva atención. Tendrá un nuevo número de turno, al final de la cola.

**La hora estimada no se cumplió.**
Es referencial: se calcula con la duración configurada del turno y se recalcula conforme avanza la cola.

**¿Por qué no puedo marcar "No se presentó"?**
Porque aún no vence la tolerancia desde el llamado. La tarjeta muestra la cuenta regresiva.

**Apareció "La atención fue modificada por otro usuario".**
Otra persona actuó sobre esa atención al mismo tiempo. La pantalla se actualizó: revise el estado e intente de nuevo si corresponde.

**Veo "No se pudo conectar con el servidor".**
Verifique su conexión a la red institucional. Si persiste, informe a TI el **código de solicitud** que aparece en el mensaje.
