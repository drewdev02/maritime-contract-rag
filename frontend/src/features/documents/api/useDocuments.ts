import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { DocumentStatus, type ContractDocument, type DocumentListResponse } from "../types/document.types";
import { useEventStreamStore } from "../store/useEventStreamStore";

interface UseDocumentsOptions {
  status?: DocumentStatus;
  refetchInterval?: number | false;
}

export const fetchDocuments = async (status?: DocumentStatus): Promise<ContractDocument[]> => {
  const response = await apiClient.get<DocumentListResponse>("/documents", {
    params: status ? { status } : undefined,
  });
  return response.data.items;
};

const DEFAULT_POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 2000;

/**
 * While the live event stream is connected, updates arrive as events and polling is only a slow
 * safety net: events are not guaranteed (the publisher can die between the commit and the publish).
 */
export const SAFETY_POLL_INTERVAL_MS = 30_000;

export const pollInterval = (
  docs: ContractDocument[] | undefined,
  connected: boolean,
  explicit?: number | false,
): number | false => {
  // Si el llamador especificó un intervalo explícito, respetarlo
  if (explicit !== undefined) {
    return explicit;
  }
  if (!docs || docs.length === 0) {
    return false;
  }

  const hasActiveWork = docs.some(
    (doc) => doc.status === DocumentStatus.PENDING || doc.status === DocumentStatus.PROCESSING,
  );
  if (!hasActiveWork) {
    return false;
  }
  return connected ? SAFETY_POLL_INTERVAL_MS : DEFAULT_POLL_INTERVAL_MS;
};

export const useDocuments = ({ status, refetchInterval }: UseDocumentsOptions = {}) => {
  const connected = useEventStreamStore((state) => state.connected);
  return useQuery({
    queryKey: ["documents", status],
    queryFn: () => fetchDocuments(status),
    refetchInterval: (query) => pollInterval(query.state.data, connected, refetchInterval),
  });
};
