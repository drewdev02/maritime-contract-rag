import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render } from "@testing-library/react";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentStatus } from "../types/document.types";

describe("DocumentStatusBadge Component", () => {
  it("renders pending status badge with clock icon and text", () => {
    const { getByTestId } = render(<DocumentStatusBadge status={DocumentStatus.PENDING} />);
    const badge = getByTestId("status-badge-pending");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Pendiente");
  });

  it("renders processing status badge with animated spinner", () => {
    const { getByTestId } = render(<DocumentStatusBadge status={DocumentStatus.PROCESSING} />);
    const badge = getByTestId("status-badge-processing");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Procesando");
  });

  it("renders ready status badge with check icon", () => {
    const { getByTestId } = render(<DocumentStatusBadge status={DocumentStatus.READY} />);
    const badge = getByTestId("status-badge-ready");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Listo");
  });

  it("renders failed status badge with error detail", () => {
    const { getByTestId } = render(
      <DocumentStatusBadge
        status={DocumentStatus.FAILED}
        errorDetail="Error al parsear páginas del PDF"
      />
    );
    const badge = getByTestId("status-badge-failed");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Fallido");
  });
});
