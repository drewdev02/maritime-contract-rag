import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useEventStreamStore } from "../store/useEventStreamStore";

/** The subset of `EventSource` this module needs, so tests can supply a fake. */
export interface EventSourceLike {
  readyState: number;
  onopen: ((event: unknown) => void) | null;
  onerror: ((event: unknown) => void) | null;
  addEventListener(type: string, listener: (event: { data: string }) => void): void;
  close(): void;
}

export type EventSourceFactory = (url: string) => EventSourceLike;

const CLOSED = 2;

export const DOCUMENT_EVENT_TYPES = [
  "document.uploaded",
  "document.processing_started",
  "document.ready",
  "document.failed",
] as const;

export interface DocumentEventPayload {
  type: (typeof DOCUMENT_EVENT_TYPES)[number];
  document_id: string;
  event_id: string;
  occurred_at: string;
  chunk_count?: number;
  reason?: string;
}

interface ConnectOptions {
  url: string;
  onOpen: () => void;
  onEvent: (event: DocumentEventPayload) => void;
  onDisconnect: () => void;
  createEventSource?: EventSourceFactory;
  reconnectDelayMs?: number;
}

/**
 * Opens the live document-events stream and keeps it open. Returns a function that closes it.
 *
 * While the stream is merely interrupted the browser reconnects on its own and resumes with
 * `Last-Event-ID`. A source that ends up CLOSED was refused by the server (for example, events are
 * disabled): it is retried after a delay instead of being abandoned.
 */
export function connectDocumentEvents({
  url,
  onOpen,
  onEvent,
  onDisconnect,
  createEventSource = (target) => new EventSource(target) as unknown as EventSourceLike,
  reconnectDelayMs = 10_000,
}: ConnectOptions): () => void {
  let source: EventSourceLike | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;

  const open = () => {
    const current = createEventSource(url);
    source = current;
    current.onopen = () => onOpen();
    current.onerror = () => {
      onDisconnect();
      if (!stopped && current.readyState === CLOSED) {
        current.close();
        timer = setTimeout(open, reconnectDelayMs);
      }
    };
    for (const type of DOCUMENT_EVENT_TYPES) {
      current.addEventListener(type, (message) => {
        try {
          onEvent(JSON.parse(message.data) as DocumentEventPayload);
        } catch {
          // A malformed frame must not break the stream.
        }
      });
    }
  };

  open();

  return () => {
    stopped = true;
    clearTimeout(timer);
    source?.close();
  };
}

interface UseDocumentEventsOptions {
  createEventSource?: EventSourceFactory;
  reconnectDelayMs?: number;
}

/**
 * Keeps the documents cache fresh from server events instead of constantly polling.
 * Mount it once, near the root. Polling stays as a safety net (see `useDocuments`).
 */
export const useDocumentEvents = (options: UseDocumentEventsOptions = {}) => {
  const queryClient = useQueryClient();
  const setConnected = useEventStreamStore((state) => state.setConnected);
  const { createEventSource, reconnectDelayMs } = options;

  useEffect(() => {
    if (!createEventSource && typeof EventSource === "undefined") {
      return;
    }
    const base = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    };

    const close = connectDocumentEvents({
      url: `${base}/documents/events`,
      // Refetch on (re)connect: anything that happened while disconnected is picked up.
      onOpen: () => {
        setConnected(true);
        refresh();
      },
      onEvent: refresh,
      onDisconnect: () => setConnected(false),
      createEventSource,
      reconnectDelayMs,
    });

    return () => {
      close();
      setConnected(false);
    };
  }, [queryClient, setConnected, createEventSource, reconnectDelayMs]);
};
