import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { PromptSuggestions } from "./PromptSuggestions";

describe("PromptSuggestions Component", () => {
  it("renders suggested maritime prompt pills", () => {
    const handleSelect = vi.fn();
    const { getByText } = render(<PromptSuggestions onSelectPrompt={handleSelect} />);

    expect(getByText("Tarifa TEU estándar")).toBeInTheDocument();
    expect(getByText("Días libres de demoras")).toBeInTheDocument();
    expect(getByText("Contenedores Reefer")).toBeInTheDocument();
  });

  it("calls onSelectPrompt when a pill is clicked", () => {
    const handleSelect = vi.fn();
    const { getByText } = render(<PromptSuggestions onSelectPrompt={handleSelect} />);

    fireEvent.click(getByText("Tarifa TEU estándar"));
    expect(handleSelect).toHaveBeenCalledWith("¿Cuál es la tarifa acordada por contenedor TEU?");
  });
});
