import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { MessageScroller } from "./MessageScroller";
import type { ChatMessage } from "@/types/chat";

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe("MessageScroller Component", () => {
  it("renders empty state with starter prompts when messages array is empty", () => {
    const handleSelectPrompt = vi.fn();
    const { getByText, getByRole } = render(
      <MessageScroller
        messages={[]}
        onSelectPrompt={handleSelectPrompt}
        isLoading={false}
      />
    );

    expect(getByText(/asistente rag de contratos marítimos/i)).toBeInTheDocument();
    const promptButton = getByRole("button", { name: /cuál es la tarifa acordada/i });
    expect(promptButton).toBeInTheDocument();

    fireEvent.click(promptButton);
    expect(handleSelectPrompt).toHaveBeenCalledWith("¿Cuál es la tarifa acordada por contenedor TEU?");
  });

  it("renders user and assistant messages with citation chips", () => {
    const messages: ChatMessage[] = [
      {
        id: "msg-1",
        sender: "user",
        text: "¿Cuál es la tarifa TEU?",
        timestamp: new Date(),
      },
      {
        id: "msg-2",
        sender: "assistant",
        text: "La tarifa base es de $1,250 USD.",
        has_sufficient_evidence: true,
        confidence_score: 0.92,
        citations: [
          {
            chunk_id: "chk-1",
            document_id: "doc-1",
            document_name: "contrato_maersk.pdf",
            page_number: 1,
            snippet_text: "Tarifa TEU: $1,250 USD",
          },
        ],
        timestamp: new Date(),
      },
    ];

    const { getByText } = render(
      <MessageScroller
        messages={messages}
        onSelectPrompt={vi.fn()}
        isLoading={false}
      />
    );

    expect(getByText("¿Cuál es la tarifa TEU?")).toBeInTheDocument();
    expect(getByText("La tarifa base es de $1,250 USD.")).toBeInTheDocument();
    expect(getByText("contrato_maersk.pdf")).toBeInTheDocument();
    expect(getByText("Similitud: 92%")).toBeInTheDocument();
  });

  it("renders sufficient evidence warning when has_sufficient_evidence is false", () => {
    const messages: ChatMessage[] = [
      {
        id: "msg-3",
        sender: "assistant",
        text: "No hay evidencia suficiente en los contratos disponibles.",
        has_sufficient_evidence: false,
        timestamp: new Date(),
      },
    ];

    const { getByText } = render(
      <MessageScroller
        messages={messages}
        onSelectPrompt={vi.fn()}
        isLoading={false}
      />
    );

    expect(getByText(/abstención por insuficiencia de evidencia/i)).toBeInTheDocument();
  });
});
