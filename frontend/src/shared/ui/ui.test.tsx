import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Field, Input, StatusBadge } from "./index";

describe("componentes base", () => {
  it("la insignia de estado comunica con texto, no solo con color", () => {
    render(<StatusBadge status="NO_PRESENTADO" />);
    const badge = screen.getByText("No presentado");
    expect(badge).toBeInTheDocument();
    expect(badge.querySelector("svg")).not.toBeNull();
  });

  it("el campo asocia etiqueta, error y aria-invalid", () => {
    render(
      <Field label="DNI" error="El DNI debe tener 8 dígitos.">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("DNI");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("El DNI debe tener 8 dígitos.");
  });
});
