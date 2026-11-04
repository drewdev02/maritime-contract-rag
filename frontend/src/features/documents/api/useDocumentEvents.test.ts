import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, createElement, type ReactNode } from "react";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  connectDocumentEvents,
  DOCUMENT_EVENT_TYPES,
  useDocumentEvents,
  type EventSourceLike,
} from "./useDocumentEvents";
import { SAFETY_POLL_INTERVAL_MS, pollInterval } from "./useDocuments";
import { DocumentStatus, type ContractDocument } from "../types/document.types";
import { useEventStreamStore } from "../store/useEventStreamStore";

class FakeEventSource implements EventSourceLike {
  static instances: FakeEventSource[] = [];
  readyState = 0;
  onopen: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  closed = false;
  private listeners = new Map<string, (event: { data: string }) => void>();

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: { data: string }) => void) {
    this.listeners.set(type, listener);
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }

  // --- test helpers ---
  open() {
    this.readyState = 1;
    this.onopen?.({});
  }
  emit(type: string, payload: unknown) {
    this.listeners.get(type)?.({ data: JSON.stringify(payload) });
  }
  emitRaw(type: string, data: string) {
    this.listeners.get(type)?.({ data });
  }
  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.({});
  }
}

const factory = (url: string) => new FakeEventSource(url);
const latest = () => FakeEventSource.instances[FakeEventSource.instances.length - 1]!;

beforeEach(() => {
  FakeEventSource.instances = [];
  useEventStreamStore.setState({ connected: false });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("connectDocumentEvents", () => {
  const options = () => ({
    url: "/api/v1/documents/events",
    onOpen: vi.fn(),
    onEvent: vi.fn(),
    onDisconnect: vi.fn(),
    createEventSource: factory,
    reconnectDelayMs: 5000,
  });

  it("listens to every document event type and passes the parsed payload on", () => {
    const o = options();
    connectDocumentEvents(o);

    for (const type of DOCUMENT_EVENT_TYPES) {
      latest().emit(type, { type, document_id: "d1" });
    }

    expect(o.onEvent).toHaveBeenCalledTimes(DOCUMENT_EVENT_TYPES.length);
    expect(o.onEvent).toHaveBeenLastCalledWith({ type: "document.failed", document_id: "d1" });
    expect(latest().url).toBe("/api/v1/documents/events");
  });

  it("ignores a malformed frame instead of breaking the stream", () => {
    const o = options();
    connectDocumentEvents(o);

    latest().emitRaw("document.ready", "{not json");
    latest().emit("document.ready", { document_id: "ok" });

    expect(o.onEvent).toHaveBeenCalledTimes(1);
    expect(o.onEvent).toHaveBeenCalledWith({ document_id: "ok" });
  });

  it("reports connection and interruption, leaving the browser to reconnect on its own", () => {
    const o = options();
    connectDocumentEvents(o);

    latest().open();
    latest().fail(0); // CONNECTING: the browser is retrying by itself

    expect(o.onOpen).toHaveBeenCalledTimes(1);
    expect(o.onDisconnect).toHaveBeenCalledTimes(1);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("retries later when the server refuses the stream (source ends up CLOSED)", () => {
    vi.useFakeTimers();
    connectDocumentEvents(options());

    latest().fail(2);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]!.closed).toBe(true);

    vi.advanceTimersByTime(5000);
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("stops for good when closed, including a pending retry", () => {
    vi.useFakeTimers();
    const close = connectDocumentEvents(options());
    latest().fail(2);

    close();
    vi.advanceTimersByTime(60_000);

    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().closed).toBe(true);
  });
});

describe("useDocumentEvents", () => {
  const setup = () => {
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);
    const hook = renderHook(() => useDocumentEvents({ createEventSource: factory }), { wrapper });
    return { invalidate, hook };
  };

  it("marks the stream connected and refetches documents when it opens", () => {
    const { invalidate } = setup();
    expect(useEventStreamStore.getState().connected).toBe(false);

    act(() => latest().open());

    expect(useEventStreamStore.getState().connected).toBe(true);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["documents"] });
  });

  it("refetches documents on every event", () => {
    const { invalidate } = setup();
    act(() => latest().open());
    invalidate.mockClear();

    act(() => latest().emit("document.ready", { document_id: "d1", chunk_count: 4 }));

    expect(invalidate).toHaveBeenCalledTimes(1);
  });

  it("falls back to polling when the connection drops and when the page unmounts", () => {
    const { hook } = setup();
    act(() => latest().open());

    act(() => latest().fail(0));
    expect(useEventStreamStore.getState().connected).toBe(false);

    act(() => latest().open());
    expect(useEventStreamStore.getState().connected).toBe(true);

    hook.unmount();
    expect(useEventStreamStore.getState().connected).toBe(false);
    expect(latest().closed).toBe(true);
  });
});

describe("pollInterval", () => {
  const doc = (status: DocumentStatus): ContractDocument =>
    ({ document_id: "d", filename: "a.pdf", status, chunk_count: 0, size_bytes: 1 }) as ContractDocument;

  it("polls fast while there is active work and no live stream", () => {
    expect(pollInterval([doc(DocumentStatus.PROCESSING)], false)).toBe(2000);
  });

  it("only keeps a slow safety poll while the live stream is connected", () => {
    expect(pollInterval([doc(DocumentStatus.PENDING)], true)).toBe(SAFETY_POLL_INTERVAL_MS);
  });

  it("does not poll when nothing is in progress or there are no documents", () => {
    expect(pollInterval([doc(DocumentStatus.READY), doc(DocumentStatus.FAILED)], false)).toBe(false);
    expect(pollInterval([], false)).toBe(false);
    expect(pollInterval(undefined, true)).toBe(false);
  });

  it("respects an explicit interval from the caller", () => {
    expect(pollInterval([doc(DocumentStatus.READY)], true, 500)).toBe(500);
    expect(pollInterval([doc(DocumentStatus.PROCESSING)], false, false)).toBe(false);
  });
});
