import { create } from "zustand";

interface EventStreamState {
  /** True while the live document-events connection (SSE) is open. */
  connected: boolean;
  setConnected: (connected: boolean) => void;
}

export const useEventStreamStore = create<EventStreamState>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),
}));
