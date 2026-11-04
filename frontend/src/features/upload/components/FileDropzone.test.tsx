import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FileDropzone } from "./FileDropzone";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
};

describe("FileDropzone Component", () => {
  it("renders upload dropzone area correctly", () => {
    const { getByText, getByTestId } = renderWithProviders(<FileDropzone />);

    expect(
      getByText(/Arrastra y suelta tu contrato PDF aquí/i)
    ).toBeInTheDocument();
    expect(getByTestId("dropzone")).toBeInTheDocument();
  });

  it("selects a valid PDF file and shows confirmation card", async () => {
    const { getByTestId, getByText } = renderWithProviders(<FileDropzone />);

    const input = getByTestId("file-input");
    const file = new File(["dummy content"], "contrato_maersk.pdf", {
      type: "application/pdf",
    });

    fireEvent.change(input, { target: { files: [file] } });

    expect(getByTestId("selected-file-card")).toBeInTheDocument();
    expect(getByText("contrato_maersk.pdf")).toBeInTheDocument();
    expect(getByText("Confirmar y Procesar")).toBeInTheDocument();
  });

  it("rejects non-PDF files and shows validation error", () => {
    const { getByTestId, getByText, queryByTestId } = renderWithProviders(<FileDropzone />);

    const input = getByTestId("file-input");
    const file = new File(["dummy content"], "imagen.png", {
      type: "image/png",
    });

    fireEvent.change(input, { target: { files: [file] } });

    expect(
      getByText(/Solo se admiten contratos en formato PDF/i)
    ).toBeInTheDocument();
    expect(queryByTestId("selected-file-card")).not.toBeInTheDocument();
  });

  it("removes selected file when clicking remove button", () => {
    const { getByTestId, getByText, getByTitle, queryByText, queryByTestId } = renderWithProviders(<FileDropzone />);

    const input = getByTestId("file-input");
    const file = new File(["dummy content"], "contrato_msc.pdf", {
      type: "application/pdf",
    });

    fireEvent.change(input, { target: { files: [file] } });
    expect(getByText("contrato_msc.pdf")).toBeInTheDocument();

    const removeBtn = getByTitle("Quitar archivo");
    fireEvent.click(removeBtn);

    expect(queryByText("contrato_msc.pdf")).not.toBeInTheDocument();
    expect(queryByTestId("selected-file-card")).not.toBeInTheDocument();
  });

  it("accepts several PDFs at once, ignores invalid ones and removes a single file", () => {
    const { getByTestId, getByText, getAllByTitle, queryByText } = renderWithProviders(<FileDropzone />);

    const input = getByTestId("file-input");
    const pdfA = new File(["a"], "a.pdf", { type: "application/pdf" });
    const pdfB = new File(["b"], "b.pdf", { type: "application/pdf" });
    const png = new File(["x"], "imagen.png", { type: "image/png" });

    fireEvent.change(input, { target: { files: [pdfA, png, pdfB] } });

    expect(getByText("a.pdf")).toBeInTheDocument();
    expect(getByText("b.pdf")).toBeInTheDocument();
    expect(queryByText("imagen.png")).not.toBeInTheDocument();
    expect(getByText(/2 contrato\(s\) listo\(s\) para subir/i)).toBeInTheDocument();

    fireEvent.click(getAllByTitle("Quitar archivo")[0]);
    expect(queryByText("a.pdf")).not.toBeInTheDocument();
    expect(getByText("b.pdf")).toBeInTheDocument();
  });
});
