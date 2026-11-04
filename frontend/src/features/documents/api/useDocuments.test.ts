import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchDocuments } from "./useDocuments";
import { apiClient } from "@/shared/api/client";
import { DocumentStatus } from "../types/document.types";

describe("useDocuments API functions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchDocuments calls /documents without params when status is undefined", async () => {
    const mockData = {
      items: [
        {
          document_id: "doc-1",
          filename: "maersk.pdf",
          status: DocumentStatus.READY,
          chunk_count: 5,
          size_bytes: 1024,
        },
      ],
      total: 1,
    };

    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue({ data: mockData });

    const result = await fetchDocuments();

    expect(getSpy).toHaveBeenCalledWith("/documents", { params: undefined });
    expect(result).toHaveLength(1);
    expect(result[0]?.document_id).toBe("doc-1");
  });

  it("fetchDocuments passes status query parameter when filtered", async () => {
    const mockData = {
      items: [],
      total: 0,
    };

    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue({ data: mockData });

    const result = await fetchDocuments(DocumentStatus.PENDING);

    expect(getSpy).toHaveBeenCalledWith("/documents", {
      params: { status: DocumentStatus.PENDING },
    });
    expect(result).toEqual([]);
  });
});
