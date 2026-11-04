import type { QueryRequest, StreamMetaEvent } from "@/types/chat";

export interface StreamChatHandlers {
  onToken: (delta: string) => void;
  onMeta: (meta: StreamMetaEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

export async function streamContractQuestion(
  req: QueryRequest,
  handlers: StreamChatHandlers,
  signal?: AbortSignal
): Promise<void> {
  const baseURL = (import.meta.env.VITE_API_URL as string) || "/api/v1";
  const url = `${baseURL}/query/stream`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    const error = new Error(`Error ${response.status}: ${errorText || response.statusText}`);
    handlers.onError?.(error);
    throw error;
  }

  if (!response.body) {
    const error = new Error("No response body received from server");
    handlers.onError?.(error);
    throw error;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        if (!block.trim()) continue;

        let eventType = "message";
        let dataStr = "";

        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5).trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === "token") {
            if (typeof parsed.delta === "string") {
              handlers.onToken(parsed.delta);
            }
          } else if (eventType === "meta") {
            handlers.onMeta(parsed as StreamMetaEvent);
          } else if (eventType === "error") {
            const err = new Error(parsed.error ?? "Unknown stream error");
            handlers.onError?.(err);
            throw err;
          } else if (eventType === "done") {
            handlers.onDone?.();
          }
        } catch (e) {
          if (eventType === "error") throw e;
          // Ignore json parse error for non-json data
        }
      }
    }

    handlers.onDone?.();
  } finally {
    reader.releaseLock();
  }
}
