// Genera src/shared/api/schema.d.ts a partir del OpenAPI del backend (sin levantar el servidor).
import { execFileSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const backend = resolve(import.meta.dirname, "../../backend");
const python = [".venv/Scripts/python.exe", ".venv/bin/python"].map((p) => resolve(backend, p)).find(existsSync);
if (!python) throw new Error("No se encontró el entorno virtual del backend (backend/.venv).");

const spec = execFileSync(
  python,
  ["-c", "import json,sys; from app.main import create_app; sys.stdout.write(json.dumps(create_app().openapi()))"],
  { cwd: backend, env: { ...process.env, PYTHONUTF8: "1", LOG_DIR: "" }, maxBuffer: 32 * 1024 * 1024 },
).toString();
const specPath = resolve(import.meta.dirname, "../openapi.json");
writeFileSync(specPath, spec);
execFileSync("npx", ["openapi-typescript", specPath, "-o", "src/shared/api/schema.d.ts"], {
  stdio: "inherit",
  shell: true,
});
