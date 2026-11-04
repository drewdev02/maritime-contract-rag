import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render } from "@testing-library/react";
import { DocumentTable } from "./DocumentTable";
import { DocumentStatus, type ContractDocument } from "../types/document.types";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, ...props }: { children: React.ReactNode; to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

const mockDocuments: ContractDocument[] = [
  {
    document_id: "11111111-1111-1111-1111-111111111111",
    filename: "contrato_maersk_2026.pdf",
    status: DocumentStatus.READY,
    chunk_count: 14,
    size_bytes: 2048576,
    error_detail: null,
    created_at: "2026-11-03T01:00:00Z",
  },
  {
    document_id: "22222222-2222-2222-2222-222222222222",
    filename: "contrato_msc_reefer.pdf",
    status: DocumentStatus.PENDING,
    chunk_count: 0,
    size_bytes: 512000,
    error_detail: null,
    created_at: "2026-11-03T01:30:00Z",
  },
  {
    document_id: "33333333-3333-3333-3333-333333333333",
    filename: "contrato_corrupto.pdf",
    status: DocumentStatus.FAILED,
    chunk_count: 0,
    size_bytes: 1200,
    error_detail: "Archivo corrupto o sin páginas legibles",
    created_at: "2026-11-03T01:40:00Z",
  },
];

describe("DocumentTable Component", () => {
  it("renders loading state when isLoading is true and documents are empty", () => {
    const { getByTestId, getByText } = render(
      <DocumentTable documents={[]} isLoading={true} />
    );

    expect(getByTestId("document-table-loading")).toBeInTheDocument();
    expect(getByText(/Cargando contratos marítimos/i)).toBeInTheDocument();
  });

  it("renders empty state when documents array is empty and not loading", () => {
    const { getByTestId, getByText } = render(
      <DocumentTable documents={[]} isLoading={false} />
    );

    expect(getByTestId("document-table-empty")).toBeInTheDocument();
    expect(
      getByText(/No se encontraron contratos registrados/i)
    ).toBeInTheDocument();
    expect(getByText(/Subir nuevo contrato/i)).toBeInTheDocument();
  });

  it("renders table with documents correctly", () => {
    const { getByTestId, getByText } = render(
      <DocumentTable documents={mockDocuments} isLoading={false} />
    );

    expect(getByTestId("documents-table")).toBeInTheDocument();

    // Filenames
    expect(getByText("contrato_maersk_2026.pdf")).toBeInTheDocument();
    expect(getByText("contrato_msc_reefer.pdf")).toBeInTheDocument();
    expect(getByText("contrato_corrupto.pdf")).toBeInTheDocument();

    // Formatted sizes
    expect(getByText("1.95 MB")).toBeInTheDocument();
    expect(getByText("500.0 KB")).toBeInTheDocument();
    expect(getByText("1.2 KB")).toBeInTheDocument();

    // Chunk counts
    expect(getByText("14 fragmentos")).toBeInTheDocument();

    // Status badges
    expect(getByTestId("status-badge-ready")).toBeInTheDocument();
    expect(getByTestId("status-badge-pending")).toBeInTheDocument();
    expect(getByTestId("status-badge-failed")).toBeInTheDocument();

    // Action button for ready document
    expect(getByText("Consultar")).toBeInTheDocument();
  });
});
