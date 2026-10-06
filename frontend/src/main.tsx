import "./styles/index.css";

import { TooltipProvider } from "@radix-ui/react-tooltip";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";

import { router } from "@/app/router";
import { applyA11y } from "@/shared/a11y/preferences";
import { createQueryClient } from "@/shared/api/queryClient";
import { AuthProvider } from "@/shared/auth/AuthProvider";
import { BrandingEffect } from "@/shared/branding/branding";

applyA11y(); // tamaño de letra y contraste guardados en este equipo, antes del primer dibujo
const queryClient = createQueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrandingEffect />
      <AuthProvider>
        <TooltipProvider>
          <RouterProvider router={router} />
          <Toaster position="bottom-right" richColors closeButton duration={5000} toastOptions={{ className: "font-sans" }} />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
