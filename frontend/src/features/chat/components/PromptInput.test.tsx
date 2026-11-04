import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { PromptInput } from "./PromptInput";

describe("PromptInput Component", () => {
  it("renders input field and submit button", () => {
    const { getByPlaceholderText, getByRole } = render(
      <PromptInput onSubmit={vi.fn()} isLoading={false} />
    );

    expect(getByPlaceholderText(/formula una pregunta/i)).toBeInTheDocument();
    expect(getByRole("button", { name: /consultar/i })).toBeInTheDocument();
  });

  it("submits query when form submit button is clicked", () => {
    const handleSubmit = vi.fn();
    const { getByPlaceholderText, getByRole } = render(
      <PromptInput onSubmit={handleSubmit} isLoading={false} />
    );

    const textarea = getByPlaceholderText(/formula una pregunta/i) as HTMLTextAreaElement;
    fireEvent.input(textarea, { target: { value: "¿Tarifas TEU?" } });
    const button = getByRole("button", { name: /consultar/i });
    fireEvent.click(button);

    expect(handleSubmit).toHaveBeenCalledWith("¿Tarifas TEU?");
  });

  it("submits query when Enter key is pressed without Shift", () => {
    const handleSubmit = vi.fn();
    const { getByPlaceholderText } = render(
      <PromptInput onSubmit={handleSubmit} isLoading={false} />
    );

    const textarea = getByPlaceholderText(/formula una pregunta/i) as HTMLTextAreaElement;
    textarea.focus();
    fireEvent.input(textarea, { target: { value: "¿Tarifas TEU?" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(handleSubmit).toHaveBeenCalledWith("¿Tarifas TEU?");
  });

  it("does not submit when Shift+Enter is pressed", () => {
    const handleSubmit = vi.fn();
    const { getByPlaceholderText } = render(
      <PromptInput onSubmit={handleSubmit} isLoading={false} />
    );

    const textarea = getByPlaceholderText(/formula una pregunta/i) as HTMLTextAreaElement;
    textarea.focus();
    fireEvent.input(textarea, { target: { value: "Línea 1" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it("disables textarea and button when loading", () => {
    const { getByPlaceholderText, getByRole } = render(
      <PromptInput onSubmit={vi.fn()} isLoading={true} />
    );

    expect(getByPlaceholderText(/formula una pregunta/i)).toBeDisabled();
    expect(getByRole("button", { name: /analizando/i })).toBeDisabled();
  });
});
