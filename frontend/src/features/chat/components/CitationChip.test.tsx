import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { CitationChip } from "./CitationChip";
import { useCitationStore } from "../store/useCitationStore";
import type { Citation } from "@/types/chat";

const sampleCitation: Citation = {
  chunk_id: "chk-001",
  document_id: "doc-001",
  document_name: "contrato_maersk_2026.pdf",
  page_number: 2,
  snippet_text: "10 días libres de demoras en terminal",
};

describe("CitationChip Component", () => {
  it("renders document name and page number correctly", () => {
    const { getByText } = render(<CitationChip citation={sampleCitation} />);

    expect(getByText("contrato_maersk_2026.pdf")).toBeInTheDocument();
    expect(getByText("Pág. 2")).toBeInTheDocument();
  });

  it("calls openCitation when clicked", () => {
    const openCitationSpy = vi.spyOn(useCitationStore.getState(), "openCitation");

    const { getByRole } = render(<CitationChip citation={sampleCitation} />);
    const button = getByRole("button");
    fireEvent.click(button);

    expect(openCitationSpy).toHaveBeenCalledWith(sampleCitation);
  });
});
