import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { DniInput, onlyDigits } from "./Form";

function Controlled() {
  const [dni, setDni] = useState("");
  return <DniInput aria-label="DNI" value={dni} onChange={(e) => setDni(e.target.value)} />;
}

function WithForm({ onValue }: { onValue: (v: string) => void }) {
  const { register, watch } = useForm<{ dni: string }>({ defaultValues: { dni: "" } });
  onValue(watch("dni"));
  return <DniInput aria-label="DNI" {...register("dni")} />;
}

describe("DniInput", () => {
  it("solo acepta dígitos y como máximo 8", async () => {
    render(<Controlled />);
    const input = screen.getByLabelText("DNI");
    await userEvent.type(input, "41a20b438-4999");
    expect(input).toHaveValue("41204384");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("maxlength", "8");
  });

  it("limpia lo que se pega (letras, guiones, espacios)", async () => {
    render(<Controlled />);
    const input = screen.getByLabelText("DNI");
    await userEvent.click(input);
    await userEvent.paste("DNI: 4120-4384");
    expect(input).toHaveValue("41204384");
  });

  it("funciona con react-hook-form (formulario de trabajadores)", async () => {
    let value = "";
    render(<WithForm onValue={(v) => (value = v)} />);
    await userEvent.type(screen.getByLabelText("DNI"), "12ab34CD5678");
    expect(screen.getByLabelText("DNI")).toHaveValue("12345678");
    expect(value).toBe("12345678");
  });

  it("onlyDigits descarta dígitos de otros alfabetos", () => {
    expect(onlyDigits("١٢٣٤٥٦٧٨")).toBe("");
    expect(onlyDigits("0123456789")).toBe("01234567");
  });
});
