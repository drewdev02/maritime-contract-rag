import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { AgentSteps } from "./AgentSteps";

describe("AgentSteps Component", () => {
  it("renders trigger with summary", () => {
    const { getByText } = render(
      <AgentSteps
        confidenceScore={0.88}
        hasSufficientEvidence={true}
        citationsCount={2}
      />
    );

    expect(getByText("Trazabilidad de Ejecución RAG")).toBeInTheDocument();
    expect(getByText("(3 etapas)")).toBeInTheDocument();
  });

  it("expands to show execution steps upon clicking trigger", () => {
    const { getByRole, getByText } = render(
      <AgentSteps
        confidenceScore={0.75}
        hasSufficientEvidence={true}
        citationsCount={3}
      />
    );

    const triggerButton = getByRole("button");
    fireEvent.click(triggerButton);

    expect(getByText(/1. Recuperación:/i)).toBeInTheDocument();
    expect(getByText(/Similitud: 75%/i)).toBeInTheDocument();
    expect(getByText(/2. Suficiencia Documental:/i)).toBeInTheDocument();
    expect(getByText(/3. Validación Anti-Alucinación:/i)).toBeInTheDocument();
    expect(getByText(/3 cita\(s\) textual\(es\) verificada\(s\)/i)).toBeInTheDocument();
  });

  it("displays abstention message when hasSufficientEvidence is false", () => {
    const { getByRole, getByText } = render(
      <AgentSteps
        confidenceScore={0.12}
        hasSufficientEvidence={false}
        citationsCount={0}
      />
    );

    const triggerButton = getByRole("button");
    fireEvent.click(triggerButton);

    expect(getByText(/Abstención declarada: no se superó el umbral/i)).toBeInTheDocument();
  });
});
