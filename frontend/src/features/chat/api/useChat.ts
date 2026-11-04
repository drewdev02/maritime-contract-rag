import { useState, useRef, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { QueryRequest, QueryResponse, StreamMetaEvent } from "@/types/chat";
import { streamContractQuestion } from "./streamChat";

export async function askContractQuestion(req: QueryRequest): Promise<QueryResponse> {
  const response = await apiClient.post<QueryResponse>("/query", req);
  return response.data;
}

export function useChat() {
  return useMutation({
    mutationFn: askContractQuestion,
  });
}

export interface StreamingChatCallbacks {
  onToken: (delta: string) => void;
  onMeta: (meta: StreamMetaEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

export function useStreamingChat() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const streamQuery = useCallback(
    async (req: QueryRequest, callbacks: StreamingChatCallbacks) => {
      stop();
      const controller = new AbortController();
      abortControllerRef.current = controller;
      setIsStreaming(true);

      try {
        await streamContractQuestion(
          req,
          {
            onToken: callbacks.onToken,
            onMeta: callbacks.onMeta,
            onError: callbacks.onError,
            onDone: () => {
              setIsStreaming(false);
              callbacks.onDone?.();
            },
          },
          controller.signal
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setIsStreaming(false);
        if (callbacks.onError && err instanceof Error) {
          callbacks.onError(err);
        }
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
          setIsStreaming(false);
        }
      }
    },
    [stop]
  );

  return {
    streamQuery,
    stop,
    isStreaming,
  };
}
