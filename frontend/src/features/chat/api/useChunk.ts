import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface ChunkDetail {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  page_number: number;
  start_char: number;
  end_char: number;
  text: string;
}

export const fetchChunk = async (documentId: string, chunkId: string): Promise<ChunkDetail> => {
  const response = await apiClient.get<ChunkDetail>(
    `/documents/${documentId}/chunks/${chunkId}`,
  );
  return response.data;
};

/** Loads the original fragment behind a citation so it can be shown in context. */
export const useChunk = (documentId: string | undefined, chunkId: string | undefined) =>
  useQuery({
    queryKey: ["chunk", documentId, chunkId],
    queryFn: () => fetchChunk(documentId as string, chunkId as string),
    enabled: Boolean(documentId && chunkId),
    staleTime: Infinity,
    retry: false,
  });

/** URL that opens the original PDF at the cited page in the browser's PDF viewer. */
export const documentPdfUrl = (documentId: string, pageNumber: number): string => {
  const base = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";
  return `${base}/documents/${documentId}/file#page=${pageNumber}`;
};
