# Hoja de ruta: qué más se puede implementar

Sistema de Gestión de Atención del Tópico de Salud — CSJ Lima
Actualizado: 06/10/2026

Este documento propone los siguientes pasos. Parte de dos fuentes: lo que pide el requerimiento original (`promptTopico.txt`, secciones 7 «Futuras fases» y 59 «Visión futura») y lo que ya funciona hoy. Se mantienen las reglas del requerimiento: crecer de forma incremental, sin funcionalidades innecesarias y **sin datos clínicos**.

**Esfuerzo estimado:** 🟢 bajo (1–2 días) · 🟡 medio (3–5 días) · 🔴 alto (1–3 semanas)

---

## 0. Lo que ya está construido

- Registro de turnos por DNI con validación de cobertura EPS, capacidad diaria y un solo turno activo por trabajador.
- Cola en tiempo real: llamar, iniciar, finalizar, no presentado (con tolerancia), cancelar, anular y devolver a la cola.
- Sedes, **consultorios**, **médicos**, horarios, cierres y capacidad del día, todo configurable desde la interfaz.
- Pantalla de sala para TV con voz (`/pantalla`) y consulta del trabajador desde el celular (`/consulta`).
- Correos automáticos (registro, aviso de proximidad, llamado, cancelación), con plantillas editables.
- Reportes con gráficos y exportación a **PDF y Excel**, más el listado nominal con permiso especial.
- Usuarios, roles y permisos por sede; auditoría inalterable con verificación de integridad.
- Importación de trabajadores desde Excel, backups diarios verificados y despliegue como servicios de Windows.

---

## 1. Antes de la puesta en marcha (no son funciones nuevas)

Son pasos para empezar a usar el sistema con datos reales.

| # | Tarea | Quién |
|---|---|---|
| 1.1 | **Recrear la base vacía** (quitar los datos de prueba) y crear el administrador definitivo | Desarrollo + TI |
| 1.2 | Cargar el **Excel real de trabajadores con EPS** desde *Importaciones* | Administrador |
| 1.3 | Crear a las **encargadas y supervisoras reales**, con sus sedes asignadas | Administrador |
| 1.4 | Registrar los **consultorios y médicos reales** de cada sede | Administrador |
| 1.5 | Confirmar con el área usuaria: tolerancia (hoy 10 min), capacidad, horario de **Anselmo Barreto** y textos de los correos | Área usuaria |
| 1.6 | Ejecutar `database\bootstrap\bootstrap.ps1` para crear la base de **verificación semanal de backups** | TI |
| 1.7 | Reinstalar Python «para todos los usuarios», para que el servicio no corra como LocalSystem (mejora de seguridad) | TI |
| 1.8 | Pedir a TI un **nombre DNS** (p. ej. `topico.csjlima.pj.gob.pe`) y un **certificado** reconocido, y pasar a HTTPS con un comando | TI |
| 1.9 | Instalar la **TV de cada sala** en modo kiosko (ver `docs/05-despliegue.md` §3.9) | TI |
| 1.10 | Capacitar a las encargadas (una hora) con el manual de usuario | Desarrollo |

---

## 2. Mejoras recomendadas de corto plazo (alto valor y bajo esfuerzo)

### 2.1 Horario por médico 🟡
Hoy el horario es por sede. Con esta mejora, cada médico tendría sus días y horas, por ejemplo: «Dra. Medina: lun–mié, 8–12».
- Al iniciar una atención, el sistema solo ofrece a los médicos que están de turno.
- La capacidad del día podría calcularse según los médicos presentes.
- Permite registrar **ausencias del médico** (vacaciones, licencia), que reducen la capacidad automáticamente.

### 2.2 Ticket impreso 🟢
Botón **Imprimir turno** en la Mesa, para impresora térmica de 80 mm o una hoja A6. El ticket llevaría turno, sede, hora estimada y un **código QR** que abre la consulta del trabajador con sus datos ya cargados. Es útil para quien llega en persona.

### 2.3 Pausa del tópico 🟢
Botón **Pausar atención** (refrigerio, emergencia, reunión), con un motivo.
- La pantalla de sala muestra «Atención en pausa — retomamos a las 13:00».
- Las horas estimadas se recalculan.
- Todo queda auditado.

### 2.4 Cierre del día con resumen 🟢
Al terminar la jornada, el botón **Cerrar día**:
- marca como «no presentado» a quienes quedaron en espera (con un motivo automático);
- genera el **PDF del día** (atendidos, médicos, tiempos);
- lo envía por correo a la supervisora.

El permiso `service_day:close` ya existe en la base de datos.

### 2.5 Panel en vivo para la supervisora 🟢
Vista de **todas las sedes a la vez**: personas en espera, en atención, tiempo de espera actual y alertas (tolerancias vencidas, capacidad llena, correos fallidos). Hoy la supervisora tiene que cambiar de sede en el selector.

### 2.6 Calificación del servicio 🟢
Al finalizar, un correo con un enlace para calificar la atención de 1 a 5 estrellas, con comentario opcional y anónimo.
- No pregunta por la salud: solo por el trato y el tiempo de espera.
- Agrega un indicador de satisfacción a los reportes.

### 2.7 Mensajes de la pantalla de sala 🟢
Varios mensajes que rotan al pie de la pantalla («Lávese las manos», campañas de salud, avisos). Se administran por sede y con fechas de vigencia.

---

## 3. Fases del requerimiento original

### Fase 2 — El trabajador solicita su atención 🔴
Portal donde el trabajador **pide su turno** desde la PC o el celular.
- Se identifica con DNI más un **código enviado a su correo institucional**, válido 10 minutos (sin contraseñas nuevas).
- Ve los cupos disponibles y la hora estimada, pide el turno y lo cancela si ya no lo necesita.
- Las encargadas lo ven en la cola con el canal «Web».
- Controles: un turno por día, límite de solicitudes y bloqueo temporal tras varias inasistencias (regla configurable).
- *Base lista:* el canal de registro, la consulta pública y las notificaciones ya existen.

### Fase 3 — Ingreso con la cuenta institucional (Active Directory / LDAP) 🟡
- El personal entraría con **su usuario y clave de Windows**, sin claves nuevas.
- Los roles y sedes seguirían administrándose en el sistema.
- Se mantiene una cuenta local de emergencia para el administrador.
- *Requiere:* que TI habilite el acceso de lectura al directorio (servidor, puerto y una cuenta de servicio).
- *Base lista:* el usuario ya está preparado para enlazarse con la cuenta del directorio.

### Fase 4 — Integraciones institucionales 🟡–🔴
- **Padrón de personal / Recursos Humanos:** sincronizar trabajadores (altas, bajas y dependencia) automáticamente, en vez de importar un Excel.
- **Cobertura EPS:** si la aseguradora o RR. HH. entregan un archivo o servicio periódico, cargarlo de forma programada.
- **Mesa de ayuda (HelpdeskLima):** registrar automáticamente las incidencias técnicas del sistema.

### Fase 5 — Más automatización de notificaciones 🟡
- **WhatsApp o SMS** para el aviso «ya casi es su turno», si la institución lo autoriza; el sistema ya está preparado para varios canales.
- Recordatorio si el trabajador fue llamado y no se acerca.
- **Alertas internas** a la supervisora: correos que no salen, capacidad agotada antes de las 10:00, tiempos de espera altos.
- Resumen semanal automático por correo, con el PDF de indicadores.

### Fase 6 — Paneles estadísticos avanzados 🟡
- Comparativos mes a mes y entre sedes, y tendencias de demanda.
- **Predicción de demanda** por día de la semana y hora, para planificar la capacidad y los turnos de los médicos.
- Indicadores por médico y por consultorio: carga y tiempos promedio.
- Mapa de calor de demanda (día de la semana × hora).
- Tablero para la Gerencia, de solo lectura.

---

## 4. Otras ideas útiles

| Idea | Valor | Esfuerzo |
|---|---|---|
| **Importar las atenciones históricas** del Excel actual (el requerimiento pide trazabilidad de la migración) | Reportes con el histórico completo | 🟡 (depende del formato del Excel) |
| **Prioridad explícita** (gestantes, adultos mayores, personas con discapacidad), como regla auditable y desactivada por defecto (§ «prioridad especial» del requerimiento) | Equidad y cumplimiento normativo | 🟡 |
| **Autoregistro en un tótem**: tablet en la entrada donde el trabajador digita su DNI y recibe su turno | Menos carga para la encargada | 🟡 (reutiliza la Fase 2) |
| **Aplicación instalable (PWA)** para la consulta del trabajador, con aviso en el celular al ser llamado | Mejor experiencia móvil (requiere HTTPS) | 🟡 |
| **Modo sin conexión de la pantalla de sala**: muestra el último estado si se corta la red | Robustez | 🟢 |
| **Reporte de gestión mensual automático** en PDF para la Gerencia | Ahorro de tiempo | 🟢 |
| **Accesibilidad**: alto contraste y tamaño de letra ajustable | Inclusión | 🟢 |
| **Identidad visual oficial** del Poder Judicial (logo, colores) en la interfaz, los correos y los PDF | Imagen institucional | 🟢 (requiere el manual de identidad) |
| **Respaldo fuera del servidor**: copia automática de los backups a otra unidad o servidor | Continuidad ante una falla del disco | 🟢 |
| **Monitoreo**: aviso a TI si el servicio cae o el disco se llena | Disponibilidad | 🟢 |

---

## 5. Orden sugerido

1. **Puesta en marcha** (sección 1): sin esto no conviene sumar funciones.
2. **Paquete operativo:** ticket impreso (2.2), pausa (2.3), cierre del día (2.4) y panel en vivo (2.5).
3. **Horario por médico** (2.1) y **atenciones históricas** (sección 4).
4. **Fase 3** (cuenta institucional), en cuanto TI dé el acceso al directorio.
5. **Fase 2** (el trabajador pide su turno), idealmente después de HTTPS.
6. Fases 5 y 6 según cómo se use el sistema y lo que pidan las áreas.

> Cada mejora se implementaría igual que hasta ahora: con su diseño, migración de base de datos, pruebas automáticas, documentación y despliegue con backup previo.

---

## 6. Decisiones que necesitamos de la institución

- ¿Se autoriza la **calificación del servicio** y el envío por **WhatsApp o SMS**?
- ¿Se requiere **prioridad especial** y para qué grupos?
- ¿Quién recibe los **resúmenes automáticos** (supervisora, Gerencia, Bienestar)?
- ¿Hay acceso a **AD/LDAP** y al padrón de **RR. HH.**?
- ¿Cuál es el formato del **Excel histórico** de atenciones?
- ¿Se cuenta con el **manual de identidad visual**?
