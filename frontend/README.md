# Frontend — Tópico de Salud CSJ Lima

Interfaz web en **React 19 + TypeScript (estricto) + Vite 8 + Tailwind 4**, con un sistema de diseño propio.

## Principios

- **Sin lógica de negocio en los componentes.** Las reglas viven en el backend. Cada atención trae sus `allowed_actions` según su estado y los permisos del usuario, así que la máquina de estados no se duplica.
- **Contrato tipado.** `src/shared/api/schema.d.ts` se genera desde el OpenAPI del backend (`npm run gen:api`). Si el backend cambia un contrato, el compilador señala cada uso afectado.
- **Seguridad:**
  - el access token vive solo en memoria;
  - la sesión se renueva con una cookie HttpOnly, en una sola solicitud aunque fallen varias a la vez;
  - `dangerouslySetInnerHTML` está prohibido por lint;
  - en producción la CSP es estricta (`script-src 'self'`).
- **Hora del servidor.** Los cronómetros (tiempo en atención, tolerancia) usan la hora del servidor, no la del PC; un equipo con la hora mal configurada no altera la operación. Las fechas se muestran siempre en America/Lima.
- **Funciona sin Internet.** Fuentes e íconos van empaquetados; no hay CDNs.
- **Accesibilidad:**
  - los estados usan texto, ícono y color;
  - las etiquetas están asociadas a sus campos;
  - diálogos accesibles (Radix), atajos de teclado (F2 buscar DNI, F4 llamar siguiente) y foco visible;
  - los gráficos usan una paleta validada para daltonismo y siempre tienen su tabla equivalente.

## Estructura

```
src/
  app/            router (carga diferida por módulo), guards, navegación, AppShell
  shared/
    api/          cliente HTTP, tipos generados, TanStack Query
    auth/         sesión (AuthProvider) y sede de trabajo (SiteProvider)
    ui/           sistema de diseño: Button, Field, DataTable, Modal, Drawer, StatusBadge, KpiCard…
    charts/       gráficos SVG sin dependencias (ColumnChart, BarList)
    lib/          formato de fechas (Lima), hora del servidor, estados, hooks
  features/
    desk/         Mesa de atención (registro por DNI, cola en vivo, llamar siguiente)
    appointments/ historial, detalle con línea de tiempo, acciones con motivo
    workers/      trabajadores y cobertura EPS
    imports/      asistente de importación de Excel
    reports/      indicadores y exportación
    audit/        auditoría y verificación de integridad
    admin/        usuarios y roles, sedes y horarios, catálogos y parámetros
    public/       consulta pública del turno (móvil)
```

## Desarrollo

```powershell
npm install
npm run gen:api        # regenera los tipos desde el backend (tras cambiar la API)
npm run dev            # http://localhost:5173 ; /api se redirige al backend
```

Variables opcionales: `VITE_API_TARGET` (URL del backend en desarrollo; por defecto `http://127.0.0.1:8000`).

> En el servidor institucional de desarrollo, los puertos 5173, 5180, 8000 y 8010 los usan otras aplicaciones. Use, por ejemplo:
> `$env:VITE_API_TARGET="http://127.0.0.1:8765"; npx vite --host 127.0.0.1 --port 5790`

## Calidad

```powershell
npm run typecheck      # TypeScript estricto
npm run lint           # ESLint (incluye reglas de hooks y anti-XSS)
npm test               # Vitest + Testing Library
npm run build          # build de producción en dist/
```

## Producción

`npm run build` genera `dist/`. El backend lo sirve en el **mismo origen** que la API: se define `FRONTEND_DIST=<ruta>/frontend/dist` en `backend/.env`. Con eso:
- hay un solo servicio que instalar;
- no se necesita CORS;
- los assets con hash llevan caché inmutable;
- `index.html` se sirve sin caché y con CSP estricta.

El proxy inverso (IIS, Caddy o Nginx) queda solo para TLS.

Navegadores soportados: Edge, Chrome o Firefox de 2023 en adelante (se actualizan solos en Windows 10/11).

## Revisión visual

`node scripts/screenshots.mjs <url> <carpeta>` recorre la aplicación con el Chrome instalado y captura cada pantalla. Útil para validar cambios de diseño y generar material del manual de usuario. Los datos de demostración se cargan con `python -m scripts.seed_demo` en el backend (nunca en producción).
