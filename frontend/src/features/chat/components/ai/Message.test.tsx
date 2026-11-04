import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render } from "@testing-library/react";
import { Message } from "./Message";
import type { ChatMessage } from "@/types/chat";

describe("Message Component", () => {
  it("renders user message with appropriate styling and text", () => {
    const userMsg: ChatMessage = {
      id: "u-1",
      sender: "user",
      text: "¿Tarifas para contenedores?",
      timestamp: new Date(),
    };

    const { getByText } = render(<Message message={userMsg} />);
    expect(getByText("¿Tarifas para contenedores?")).toBeInTheDocument();
  });

  it("renders assistant message with AgentSteps, similarity badge, and citations", () => {
    const assistantMsg: ChatMessage = {
      id: "a-1",
      sender: "assistant",
      text: "La tarifa acordada es de $1,400 USD.",
      confidence_score: 0.95,
      has_sufficient_evidence: true,
      citations: [
        {
          chunk_id: "c-1",
          document_id: "d-1",
          document_name: "acuerdo_maersk.pdf",
          page_number: 3,
          snippet_text: "Flete fijado en $1,400 USD por TEU.",
        },
      ],
      timestamp: new Date(),
    };

    const { getByText } = render(<Message message={assistantMsg} />);
    expect(getByText("Asistente Naviera Portecho")).toBeInTheDocument();
    expect(getByText("La tarifa acordada es de $1,400 USD.")).toBeInTheDocument();
    expect(getByText("Similitud: 95%")).toBeInTheDocument();
    expect(getByText("Razonamiento y trazabilidad RAG")).toBeInTheDocument();
    expect(getByText("acuerdo_maersk.pdf")).toBeInTheDocument();
  });
});
