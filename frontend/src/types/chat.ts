export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  snippet_text: string;
}

export interface QueryRequest {
  query: string;
  top_k?: number;
  document_id?: string;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  has_sufficient_evidence: boolean;
  confidence_score?: number | null;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  citations?: Citation[];
  has_sufficient_evidence?: boolean;
  confidence_score?: number | null;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface StreamMetaEvent {
  citations: Citation[];
  has_sufficient_evidence: boolean;
  confidence_score?: number | null;
}

