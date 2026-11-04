export enum DocumentStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  READY = "ready",
  FAILED = "failed",
}

export interface ContractDocument {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  chunk_count: number;
  size_bytes: number;
  error_detail?: string | null;
}

export interface ContractDocumentListResponse {
  items: ContractDocument[];
  total: number;
}
