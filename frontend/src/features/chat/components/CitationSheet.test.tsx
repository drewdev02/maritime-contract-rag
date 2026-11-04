import { beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { act, render, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { CitationSheet, splitAroundSnippet } from "./CitationSheet";
import { useCitationStore } from "../store/useCitationStore";

vi.mock("@/shared/api/client", () => ({ apiClient: { get: vi.fn() } }));

const citation = {
  chunk_id: "chunk-1",
  document_id: "doc-1",
  document_name: "maersk.pdf",
  page_number: 2,
  snippet_text: "7 días libres",
};

// The sheet renders in a portal on document.body. `screen` stays bound to the document that
// existed before happy-dom's GlobalRegistrator replaced it, so query the live body instead.
const screen = {
  getByTestId: (id: string) => within(document.body).getByTestId(id),
  getByText: (text: string | RegExp) => within(document.body).getByText(text),
};

// happy-dom's MutationObserver is incompatible with Testing Library's waitFor/findBy,
// so pending promises (react-query) are flushed explicitly instead.
const flush = async () => {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
};

const renderSheet = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CitationSheet />
    </QueryClientProvider>,
  );
  act(() => useCitationStore.getState().openCitation(citation));
};

describe("CitationSheet", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    useCitationStore.setState({ activeCitation: null, isOpen: false });
  });

  it("loads the original fragment, highlights the cited text and links to the PDF page", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        ...citation,
        chunk_index: 3,
        start_char: 10,
        end_char: 80,
        text: "Cláusula 4. El cliente dispone de 7 días libres en terminal.",
      },
    });

    renderSheet();

    await flush();
    const text = screen.getByTestId("chunk-text");
    expect(apiClient.get).toHaveBeenCalledWith("/documents/doc-1/chunks/chunk-1");
    expect(text).toHaveTextContent("Cláusula 4. El cliente dispone de 7 días libres en terminal.");
    expect(text.querySelector("mark")).toHaveTextContent("7 días libres");
    expect(screen.getByText(/página 2 · posición 10-80/)).toBeInTheDocument();
    expect(screen.getByTestId("open-pdf-link")).toHaveAttribute(
      "href",
      expect.stringMatching(/\/documents\/doc-1\/file#page=2$/),
    );
  });

  it("falls back to the cited snippet when the fragment cannot be loaded", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("404"));

    renderSheet();

    await flush();
    expect(screen.getByTestId("chunk-error")).toBeInTheDocument();
    expect(screen.getByText("7 días libres")).toBeInTheDocument();
    expect(screen.getByTestId("open-pdf-link")).toBeInTheDocument();
  });
});

describe("splitAroundSnippet", () => {
  it("is case-insensitive and returns null when the snippet is absent", () => {
    expect(splitAroundSnippet("Hay 7 DÍAS LIBRES hoy", "7 días libres")).toEqual({
      before: "Hay ",
      match: "7 DÍAS LIBRES",
      after: " hoy",
    });
    expect(splitAroundSnippet("otro texto", "7 días libres")).toBeNull();
  });
});
