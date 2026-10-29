/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, /api se redirige al backend: el navegador ve un solo origen,
// igual que en producción (proxy inverso). Así no se necesita CORS y la cookie
// de sesión (SameSite=Strict, Path=/api/v1/auth) funciona sin cambios.
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:42001";

// Versión visible en la interfaz: la de package.json (igual a la del backend, pyproject.toml;
// una prueba del backend verifica que coincidan).
const APP_VERSION = `v${(JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as { version: string }).version}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { __APP_VERSION__: JSON.stringify(APP_VERSION) },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 42000,
    strictPort: true,
    proxy: { "/api": { target: API_TARGET, changeOrigin: false } },
  },
  build: {
    target: "es2022",
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
