import { TooltipProvider } from "@radix-ui/react-tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown } | undefined;

/** Simula el backend: cada handler decide la respuesta según método + ruta. */
export function mockApi(...handlers: Handler[]) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost");
    const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
    calls.push({ method: init.method ?? "GET", path: url.pathname, body });
    for (const handler of handlers) {
      const result = handler(url, init);
      if (result) {
        return new Response(result.body === undefined ? null : JSON.stringify(result.body), {
          status: result.status ?? 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "test-request" },
        });
      }
    }
    return new Response(JSON.stringify({ code: "NOT_FOUND", message: "No encontrado" }), { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}

export const route =
  (method: string, path: string, body: unknown, status = 200): Handler =>
  (url, init) =>
    (init.method ?? "GET") === method && url.pathname === `/api/v1${path}` ? { status, body } : undefined;

export function renderWithProviders(ui: ReactElement, { path = "/" }: { path?: string } = {}): RenderResult {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper });
}
