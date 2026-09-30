// Capturas de pantalla para revisión visual (usa el Chrome instalado; no descarga navegadores).
// Uso: node scripts/screenshots.mjs <baseUrl> <outDir> [escenario...]
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { chromium } from "playwright-core";

const [, , baseUrl = "http://127.0.0.1:5790", outDir = "screenshots", ...only] = process.argv;
const CHROME = process.env.CHROME_PATH ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const USER = process.env.DEMO_USER ?? "encargada.alz";
const PASSWORD = process.env.DEMO_PASSWORD ?? "Demo-Topico-2026";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-proxy-server"] });
const shot = async (page, name, fullPage = false) => {
  await page.waitForTimeout(400);
  await page.screenshot({ path: resolve(outDir, `${name}.png`), fullPage });
  console.log("captura:", name);
};
const want = (name) => only.length === 0 || only.includes(name);

async function loggedIn(viewport, user = USER) {
  const context = await browser.newContext({ viewport, locale: "es-PE", timezoneId: "America/Lima", ignoreHTTPSErrors: true });
  const page = await context.newPage();
  page.on("pageerror", (e) => console.error("ERROR JS:", e.message));
  page.on("console", (m) => m.type() === "error" && console.error("consola:", m.text()));
  await page.goto(`${baseUrl}/login`);
  await page.getByLabel("Usuario").fill(user);
  await page.getByLabel("Contraseña", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  return { context, page };
}

if (want("login")) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-PE", ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/login`);
  await shot(page, "01-login");
  await context.close();
}

if (want("mesa")) {
  const { context, page } = await loggedIn({ width: 1440, height: 900 });
  await page.goto(`${baseUrl}/mesa`);
  await page.getByText("En espera").first().waitFor();
  await shot(page, "02-mesa", true);
  await page.getByLabel("DNI del trabajador").fill(process.env.DEMO_DNI ?? "41204384");
  await page.getByText(/Habilitado|no cuenta|No existe/).first().waitFor();
  await shot(page, "03-mesa-dni");
  await context.close();
}

if (want("tablet")) {
  const { context, page } = await loggedIn({ width: 1024, height: 768 });
  await page.goto(`${baseUrl}/mesa`);
  await page.getByText("En espera").first().waitFor();
  await shot(page, "04-mesa-tablet");
  await context.close();
}

async function tour(user, pages, viewport = { width: 1440, height: 900 }) {
  const { context, page } = await loggedIn(viewport, user);
  for (const [name, path, waitFor, action] of pages) {
    if (!want(name)) continue;
    await page.goto(`${baseUrl}${path}`);
    if (waitFor) await page.getByText(waitFor).first().waitFor({ timeout: 15000 });
    if (action) await action(page);
    await shot(page, name, true);
  }
  await context.close();
}

await tour("supervisor.demo", [
  ["05-atenciones", "/atenciones", "Historial de solicitudes"],
  ["06-atencion-detalle", "/atenciones", "Historial de solicitudes", async (p) => {
    await p.locator("tbody tr").first().click();
    await p.getByText("Línea de tiempo").waitFor();
  }],
  ["07-reportes", "/reportes", "Resultado diario"],
  ["08-sedes", "/admin/sedes", "Configuración vigente"],
  ["09-sedes-horario", "/admin/sedes", "Configuración vigente", async (p) => {
    await p.getByRole("tab", { name: "Horario" }).click();
    await p.getByText("Horario semanal").waitFor();
  }],
]);
await tour("admin.demo", [
  ["10-trabajadores", "/trabajadores", "trabajadores"],
  ["11-importaciones", "/importaciones", "Historial de importaciones"],
  ["12-usuarios", "/admin/usuarios", "Nuevo usuario"],
  ["13-roles", "/admin/usuarios", "Nuevo usuario", async (p) => {
    await p.getByRole("tab", { name: "Roles y permisos" }).click();
    await p.getByText("Cada cambio de permisos").waitFor();
  }],
  ["14-plantillas", "/admin/configuracion", "Motivos administrativos", async (p) => {
    await p.getByRole("tab", { name: "Plantillas de correo" }).click();
    await p.getByText("Variables").waitFor();
  }],
]);
await tour("auditor.demo", [["15-auditoria", "/auditoria", "Registro inalterable"]]);

if (want("16-consulta-movil")) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "es-PE", isMobile: true, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/consulta`);
  await page.getByLabel("DNI").fill(process.env.PUBLIC_DNI ?? "41200137");
  await page.getByLabel("Código de turno").fill(process.env.PUBLIC_CODE ?? "A-010");
  await page.getByRole("button", { name: "Consultar" }).click();
  await page.getByText(/Posición|Su atención|turno/).first().waitFor();
  await shot(page, "16-consulta-movil", true);
  await context.close();
}

if (want("17-turno-registrado") || want("18-cancelar")) {
  const { context, page } = await loggedIn({ width: 1440, height: 900 });
  await page.goto(`${baseUrl}/mesa`);
  await page.getByText("En espera").first().waitFor();
  if (want("17-turno-registrado")) {
    await page.getByLabel("DNI del trabajador").fill(process.env.REGISTER_DNI ?? "41204384");
    await page.getByText("Habilitado · EPS Rímac vigente").waitFor();
    await page.getByRole("button", { name: /Registrar turno/ }).click();
    await page.getByText("Turno registrado").waitFor();
    await shot(page, "17-turno-registrado");
  }
  if (want("18-cancelar")) {
    await page.getByRole("button", { name: /Acciones del turno/ }).last().click();
    await page.getByRole("menuitem", { name: "Cancelar" }).click();
    await page.getByText("Motivo").first().waitFor();
    await page.waitForTimeout(500);
    await shot(page, "18-cancelar");
  }
  await context.close();
}

await browser.close();
