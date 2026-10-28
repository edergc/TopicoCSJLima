# Guion de demostración — Sistema del Tópico de Salud CSJ Lima

Presentación ante la Presidencia de la Corte y el Directorio · Versión del 28/10/2026

---

## 1. Objetivo y mensaje clave

Mostrar en 10 a 12 minutos que la primera etapa del sistema ya funciona de punta a punta: registro de la atención, llamado en la sala, consulta del trabajador, supervisión en vivo, reportes y auditoría.

**Mensaje clave (decirlo al inicio y al cierre):** «El Tópico de Salud pasa de un registro en Excel a un sistema institucional con cola en tiempo real, trazabilidad completa y reportes para la toma de decisiones, sin almacenar datos clínicos.»

- **Público:** Presidencia de la Corte y Directorio.
- **Duración:** 10–12 minutos de recorrido + 5–10 minutos de preguntas.
- **Presentan:** una persona maneja el sistema y otra narra; quien narra sigue este guion.
- **Datos:** todos los trabajadores y atenciones de la demostración son ficticios. Decirlo al empezar.

---

## 2. Preparación

Todo debe quedar abierto y probado 30 minutos antes; durante la presentación no se escriben direcciones ni contraseñas a la vista.

### Equipos

| Equipo | Qué muestra | Dirección / acción |
| --- | --- | --- |
| Laptop principal (proyector) | Mesa de atención, panel, reportes, auditoría | http://172.20.1.51:42000 |
| Segunda pantalla o TV | Pantalla de sala | http://172.20.1.51:42000/pantalla/alz → «Iniciar pantalla» (con sonido) |
| Celular con Wi-Fi institucional | Consulta del trabajador (QR del ticket) | Cámara del celular |
| Impresora (opcional) | Ticket impreso | Configurada como predeterminada en la laptop |

### Cuentas de la demostración

Entregar en papel a quien maneja el sistema; no proyectar.

| Usuario | Rol | Para |
| --- | --- | --- |
| 40000003 | Encargada — Alzamora Valdez | Mesa de atención |
| 40000002 | Supervisora — ambas sedes | Panel en vivo, reportes, cierre del día |
| 40000005 | Auditor | Auditoría |

### El día anterior

- [ ] Finalizar la atención pendiente del 27/10 en Alzamora (como 40000002, en *Atenciones*) para que ese día se cierre solo.
- [ ] Ejecutar `deploy\windows\status.ps1` en el servidor: todo debe salir «OK».
- [ ] Probar la red de la sala: la laptop y el celular deben abrir http://172.20.1.51:42000.
- [ ] Ensayar el recorrido completo una vez, cronometrado.

### La mañana de la presentación (elegir una)

- [ ] **Opción A, recomendada:** no cargar nada y registrar en vivo; impresiona más ver el flujo desde cero.
- [ ] **Opción B:** ejecutar `CARGAR-DATOS-DE-PRUEBA.bat` para tener una cola del día ya en marcha.

### 30 minutos antes

- [ ] Laptop: iniciar sesión como 40000003 en la *Mesa de atención*; en otra ventana de incógnito, como 40000002 en *Panel en vivo* (para que las sesiones no se mezclen).
- [ ] TV: pantalla de sala iniciada, volumen alto; probar el sonido con un llamado.
- [ ] Tener a mano DNI de trabajadores ficticios: **41204384** (con correo) y **41200959** (sin cobertura EPS, para mostrar el rechazo); otros se toman de la lista *Trabajadores*.
- [ ] Cerrar notificaciones, correo y chats de la laptop; zoom del navegador al 100 % y pantalla completa (F11).
- [ ] Nota: el navegador mostrará «No es seguro» junto a la dirección porque la red interna usa HTTP; ver la respuesta en *Preguntas probables*.

---

## 3. Recorrido paso a paso

Nueve pasos en unos 12 minutos; el momento central es el paso 4, cuando la sala escucha el llamado.

| # | Min. | En pantalla (quien maneja) | Qué decir (quien narra) |
| --- | --- | --- | --- |
| 1 | 0:00 | Pantalla de inicio de sesión con el logo de la Corte | «Este es el Sistema del Tópico de Salud. Cada persona ingresa con su DNI; todo lo que hace queda registrado. Los datos que verán son ficticios.» |
| 2 | 0:45 | Mesa de atención (40000003): indicadores del día, consultorios y cola | «Esta es la mesa de la encargada del tópico. Arriba ve en todo momento los cupos libres, quién espera y quién está en atención.» |
| 3 | 1:30 | Escribir el DNI 41204384 → «Habilitado · EPS Rímac vigente» → *Registrar turno* → *Imprimir turno* | «Con el DNI, el sistema verifica al instante la cobertura del seguro y asigna el turno en orden de llegada. El ticket lleva un código QR.» Registrar 2 o 3 DNI más para tener cola. |
| 4 | 3:30 | *Llamar siguiente* (F4) → la TV suena y anuncia el turno y el consultorio | «El trabajador ya no necesita estar pendiente en la puerta: la pantalla de la sala lo llama por su turno, con voz, e indica a qué consultorio acercarse. Solo muestra el nombre abreviado.» |
| 5 | 5:00 | Celular: escanear el QR del ticket → posición y hora estimada | «Desde su celular, el trabajador ve su posición y la hora aproximada. También recibe avisos por correo cuando su turno se acerca.» |
| 6 | 6:00 | Mesa: *Iniciar atención* (elegir médico) → *Finalizar atención* | «Queda registrado quién atendió, en qué consultorio y cuánto duró la atención. No se registra ningún dato clínico.» |
| 7 | 7:00 | Panel en vivo (40000002): ambas sedes a la vez | «La supervisión ve las dos sedes en tiempo real: espera actual, atenciones en curso y alertas, sin estar físicamente en el tópico.» |
| 8 | 8:30 | Reportes (últimos 30 días) → *Exportar* → *PDF* | «Estos indicadores sustentan decisiones: demanda por día y por hora, uso de cupos, inasistencia, atenciones por médico y satisfacción del personal. Se descargan en PDF o Excel con un clic.» Mostrar el PDF abierto. |
| 9 | 10:30 | Auditoría (40000005) → *Verificar integridad* | «Cada acción queda en una auditoría que no se puede alterar: el sistema verifica su integridad y detectaría cualquier modificación.» |

**Si sobra tiempo (opcional):** registrar el DNI 41200959 para mostrar que se rechaza a quien no tiene cobertura EPS; activar el alto contraste o la letra grande con el botón *T*; mostrar *Sedes y horarios* (sedes, consultorios, médicos y horarios configurables sin programar).

---

## 4. Preguntas probables

Respuestas breves; si una pregunta pide un dato que no está aquí, anotarla y responder después.

| Pregunta | Respuesta sugerida |
| --- | --- |
| ¿Se guarda información de salud del personal? | No. Solo datos administrativos: turno, horarios, sede, consultorio y médico. El sistema impide registrar diagnósticos o síntomas. |
| ¿Quién puede ver qué? | Cada rol ve solo lo suyo y solo su sede: encargada, supervisión, auditoría y administración. Los listados con nombres requieren un permiso especial y su descarga queda auditada. |
| ¿Y si alguien modifica o borra un registro? | Las atenciones no se borran: se cancelan o anulan con motivo. La auditoría registra usuario, fecha e IP de cada acción y verifica automáticamente que nadie la altere. |
| ¿Por qué el navegador dice «No es seguro»? | Porque funciona en la red interna por HTTP. El paso a HTTPS está preparado y toma un comando cuando TI asigne un nombre y un certificado institucional. |
| ¿Qué pasa si se cae el servidor o se pierden datos? | Backup automático cada noche y una prueba semanal que restaura el backup para confirmar que sirve. Los servicios se reinician solos al encender el servidor. |
| ¿Cuánto costó? ¿Qué licencias usa? | Se desarrolló internamente con software libre (PostgreSQL, Python, React) sobre un servidor existente de la Corte; no requiere licencias. *(Confirmar antes de presentar.)* |
| ¿Se puede usar en otras sedes? | Sí. Las sedes, consultorios, médicos y horarios se crean desde el sistema, sin programar. |
| ¿El trabajador puede pedir su turno desde su celular? | Hoy consulta su turno y recibe avisos por correo. Que lo pida directamente es la siguiente etapa (Fase 2). |
| ¿Se puede dar prioridad a gestantes o adultos mayores? | Sí, está implementado como regla explícita y auditada, desactivada por defecto hasta que la institución lo apruebe. |
| ¿Cuándo puede empezar a usarse? | Tras cargar el padrón real de trabajadores con EPS, crear los usuarios del personal y capacitar a las encargadas (1 hora). |

---

## 5. Plan B

Ante cualquier falla, no diagnosticar frente al público: aplicar la salida y continuar con el siguiente paso.

| Si ocurre… | Hacer |
| --- | --- |
| La TV no suena | Seguir: el llamado igual se ve en la TV y en la mesa. Explicar que el sonido se activa con «Iniciar pantalla». |
| La TV no actualiza («Reconectando») | Recargar la página de la TV (F5) y pulsar «Iniciar pantalla». |
| El celular no abre la consulta | Abrir http://172.20.1.51:42000/consulta en la laptop e ingresar el DNI y el turno a mano. |
| No imprime el ticket | Mostrar el ticket en pantalla y continuar; la impresión es opcional. |
| «Su sesión ha finalizado» | Volver a ingresar con el mismo usuario; no se pierde nada de lo registrado. |
| La página no carga | En el servidor: `deploy\windows\status.ps1`; si algo falla, `Restart-Service TopicoCSJ-API -Force; Start-Service TopicoCSJ-Web`. Mientras tanto, mostrar el PDF de reportes ya descargado. |
| Se acaba el tiempo | Saltar al paso 8 (reportes) y cerrar con el mensaje clave. |

- [ ] Llevar descargado el PDF de reportes de los últimos 30 días, como respaldo.

---

## 6. Cierre (1–2 minutos)

Cerrar pidiendo las decisiones que permiten pasar al uso real; repetir el mensaje clave al final.

### Lo logrado en la primera etapa

- Atención del tópico en orden de registro, con cola en tiempo real en dos sedes.
- Pantalla de sala con llamado por voz, consulta del turno en el celular y avisos por correo.
- Supervisión en vivo, reportes en PDF y Excel, y auditoría inalterable.
- Sedes, consultorios, médicos y horarios configurables por la propia institución.

### Decisiones que se solicitan al Directorio *(propuesta; ajustar antes de presentar)*

1. Aprobar el inicio de uso en las sedes Javier Alzamora Valdez y Anselmo Barreto.
2. Encargar a TI un nombre de red y un certificado institucional para trabajar con HTTPS.
3. Definir si se habilita la atención prioritaria (gestantes, adultos mayores, personas con discapacidad).
4. Autorizar el acceso al padrón de personal con EPS para la carga inicial y su actualización.

### Próximos pasos

1. Carga del padrón real, creación de usuarios y capacitación de las encargadas (1 hora).
2. Inicio del uso real con acompañamiento de TI la primera semana.
3. Fase 2: el trabajador solicita su turno desde su celular. Fase 3: ingreso con la cuenta institucional de Windows.

**Mensaje final:** «Con este sistema, la Corte cuenta con información confiable y en tiempo real sobre la atención de salud de su personal, con orden, transparencia y protección de datos.»
